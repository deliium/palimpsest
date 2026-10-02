"""Owner-scoped norm beliefs inferred from witnessed behavior.

A ledger is a private expectation, not a world rule, a semantic belief, a
relationship profile, or an analysis rate. Updates read one owner's
observation, previous ledger, and identity projection. They do not read world
authority, another owner's ledger, or a metric document.
"""

from __future__ import annotations

import hashlib
import itertools
import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Final

from agents.cognition.models import ActionDirection, OwnerSafeSocialIdentity
from agents.models import AgentId
from world.identifiers import EntityId, require_exact_nonneg_int
from world.observations import Observation, ObservedCommunication, ObservedOccurrence
from world.values import ResourceKind

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.social_norms")

SOCIAL_NORM_POLICY_VERSION: Final[str] = "social-norms.v1"
_QUANTUM: Final[Decimal] = Decimal("0.000001")
_ACTIVE_CONFIDENCE: Final[float] = 0.40
_ENFORCE_CONFIDENCE: Final[float] = 0.50
_RETIRE_CONFIDENCE: Final[float] = 0.20
_DECAY: Final[float] = 0.05
_CONFORMING_DELTA: Final[float] = 0.15
_VIOLATION_DELTA: Final[float] = -0.20
_PENALTY: Final[float] = 0.35
_CONFORMING_COUNT: Final[int] = 3
_RETURN_WINDOW: Final[int] = 8
_SPARE_WINDOW: Final[int] = 1
_UTTERANCE_INTERVAL: Final[int] = 4
_EXCLUSION_WINDOW: Final[int] = 8
_SCARCITY_QUANTITY: Final[float] = 1.0
_CRITICAL_NEED: Final[float] = 0.75
_TRUST_DELTA: Final[float] = -0.25
_MAX_BELIEFS: Final[int] = 8
_MAX_EVIDENCE: Final[int] = 32
_MAX_SUPPORTERS: Final[int] = 8
_RETALIATION_LOOKBACK: Final[int] = 2
_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")
_LOCATION_OBJECT: Final[str] = "location"
_UNREFERENCED: Final[str] = "unreferenced"
_FORBIDDEN_TYPES: Final[frozenset[str]] = frozenset(
    {"WorldState", "WorldEvent", "PhysicalRules", "AgentBody", "MetricDocument"}
)
_OWN_ACT_ONLY: Final[frozenset[str]] = frozenset(
    {"refusal", "reduced_trust", "exclusion"}
)
_NOTICE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "cap_exceeded",
        "ignored_kind",
        "unresolved_entity",
        "no_candidate",
        "candidate_only",
        "utterance_interval",
        "below_count",
        "below_confidence",
        "sanction_latent",
        "sanction_unavailable",
        "no_profile",
        "trust_revision_skipped",
    }
)
_KNOWN_KINDS: Final[frozenset[str]] = frozenset({"give", "sleep", "attack"})


class NormPattern(StrEnum):
    """Closed behavior a private expectation can be about."""

    RETURN_TRANSFER = "return_transfer"
    SHARE_UNDER_SCARCITY = "share_under_scarcity"
    SPARE_AFTER_SLEEP = "spare_after_sleep"
    RECIPROCAL_EXCHANGE = "reciprocal_exchange"


class NormExpectation(StrEnum):
    """Closed action token stored on a belief. The world does not check it."""

    GIVE_BACK = "give_back"
    GIVE = "give"
    WITHHOLD_ATTACK = "withhold_attack"
    GIVE_AGAIN = "give_again"


class NormStatus(StrEnum):
    """Closed lifecycle for one owner's belief."""

    CANDIDATE = "candidate"
    ACTIVE = "active"
    RETIRED = "retired"


class NormResponse(StrEnum):
    """Closed choice for one active belief this tick."""

    FOLLOW = "follow"
    IGNORE = "ignore"
    VIOLATE = "violate"
    COMMUNICATE = "communicate"
    ENFORCE = "enforce"


class NormSanction(StrEnum):
    """Closed sanction an owner may witness or apply."""

    CRITICISM = "criticism"
    REFUSAL = "refusal"
    REDUCED_TRUST = "reduced_trust"
    RETALIATION = "retaliation"
    EXCLUSION = "exclusion"


class NormConsequenceChannel(StrEnum):
    """Closed provenance for one perceived consequence."""

    WITNESSED = "witnessed"
    OWN_ACT = "own_act"


class NormEvidenceChannel(StrEnum):
    """Closed evidence sign for one ledger item."""

    CONFORMING = "conforming"
    VIOLATION = "violation"


_EXPECTATION_FOR: Final[Mapping[NormPattern, NormExpectation]] = {
    NormPattern.RETURN_TRANSFER: NormExpectation.GIVE_BACK,
    NormPattern.SHARE_UNDER_SCARCITY: NormExpectation.GIVE,
    NormPattern.SPARE_AFTER_SLEEP: NormExpectation.WITHHOLD_ATTACK,
    NormPattern.RECIPROCAL_EXCHANGE: NormExpectation.GIVE_AGAIN,
}
_PATTERN_TOKENS: Final[frozenset[str]] = frozenset(item.value for item in NormPattern)


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "norm_validation_failed field=%s reason_code=%s",
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


def _finite(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise _fail(field_name, "not_finite")
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


def _require_tuple(field_name: str, values: object) -> tuple[object, ...]:
    if isinstance(values, (str, bytes, set, frozenset)) or not isinstance(
        values, Sequence
    ):
        raise _fail(field_name, "invalid_type")
    return tuple(values)


def _sign(before: float, after: float) -> str:
    if after > before:
        return "positive"
    if after < before:
        return "negative"
    return "zero"


def norm_belief_id(
    owner_id: AgentId,
    pattern: NormPattern,
    counterpart_ids: Sequence[AgentId] = (),
) -> str:
    """sha256 of owner id, pattern, and sorted counterpart ids when present."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(pattern) is not NormPattern:
        raise _fail("pattern", "unknown_pattern")
    parts = [owner_id.value, pattern.value]
    if counterpart_ids:
        parts.append(",".join(sorted(agent.value for agent in counterpart_ids)))
    return _sha256_hex("|".join(parts))


def norm_evidence_id(
    belief_id: str,
    ordinal: int,
    channel: NormEvidenceChannel,
    lineage_ref: str,
) -> str:
    """sha256 of belief id, ordinal, channel, and lineage ref."""
    head = _require_hex_id("belief_id", belief_id)
    if isinstance(ordinal, bool) or type(ordinal) is not int or ordinal < 0:
        raise _fail("ordinal", "invalid_type")
    if type(channel) is not NormEvidenceChannel:
        raise _fail("channel", "unknown_channel")
    if not isinstance(lineage_ref, str) or not lineage_ref:
        raise _fail("lineage_ref", "invalid_type")
    return _sha256_hex(f"{head}|{ordinal}|{channel.value}|{lineage_ref}")


def _reject_forbidden(value: object) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    name = type(value).__name__
    module = type(value).__module__
    if (
        name in _FORBIDDEN_TYPES
        or module.startswith("analysis")
        or module.startswith("analysis.")
    ):
        raise TypeError(f"{name}: forbidden_input")


@dataclass(frozen=True, slots=True)
class NormContext:
    """Situation in which one expectation applies. Matching uses the observation."""

    pattern: NormPattern
    location_id: EntityId | None = None
    counterpart_id: AgentId | None = None
    window_until_tick: int | None = None

    def __post_init__(self) -> None:
        if type(self.pattern) is not NormPattern:
            raise _fail("context.pattern", "unknown_pattern")
        if self.location_id is not None and type(self.location_id) is not EntityId:
            raise _fail("context.location_id", "invalid_type")
        if self.counterpart_id is not None and type(self.counterpart_id) is not AgentId:
            raise _fail("context.counterpart_id", "invalid_type")
        if self.pattern is NormPattern.SHARE_UNDER_SCARCITY:
            if self.counterpart_id is not None:
                raise _fail("context.counterpart_id", "unexpected_counterpart")
        elif self.location_id is not None:
            raise _fail("context.location_id", "unexpected_location")
        if self.window_until_tick is not None:
            object.__setattr__(
                self,
                "window_until_tick",
                require_exact_nonneg_int(
                    "NormContext.window_until_tick", self.window_until_tick
                ),
            )


@dataclass(frozen=True, slots=True)
class NormEvidenceItem:
    """One witnessed conforming or violating item on a belief."""

    evidence_id: str
    ordinal: int
    channel: NormEvidenceChannel
    lineage_ref: str
    tick: int
    actor_id: AgentId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "evidence_id", _require_hex_id("evidence_id", self.evidence_id)
        )
        if isinstance(self.ordinal, bool) or type(self.ordinal) is not int:
            raise _fail("evidence.ordinal", "invalid_type")
        if self.ordinal < 0:
            raise _fail("evidence.ordinal", "out_of_range")
        if type(self.channel) is not NormEvidenceChannel:
            raise _fail("evidence.channel", "unknown_channel")
        if not isinstance(self.lineage_ref, str) or not self.lineage_ref:
            raise _fail("evidence.lineage_ref", "invalid_type")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("NormEvidenceItem.tick", self.tick),
        )
        if self.actor_id is not None and type(self.actor_id) is not AgentId:
            raise _fail("evidence.actor_id", "invalid_type")


@dataclass(frozen=True, slots=True)
class NormConsequence:
    """One perceived sanction, stored only with a channel."""

    sanction: NormSanction
    channel: NormConsequenceChannel
    tick: int
    actor_id: AgentId | None = None

    def __post_init__(self) -> None:
        if type(self.sanction) is not NormSanction:
            raise _fail("consequence.sanction", "unknown_sanction")
        if type(self.channel) is not NormConsequenceChannel:
            raise _fail("consequence.channel", "unknown_channel")
        if (
            self.sanction.value in _OWN_ACT_ONLY
            and self.channel is NormConsequenceChannel.WITNESSED
        ):
            raise _fail("consequence.channel", "witnessed_forbidden")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("NormConsequence.tick", self.tick),
        )
        if self.actor_id is not None and type(self.actor_id) is not AgentId:
            raise _fail("consequence.actor_id", "invalid_type")


@dataclass(frozen=True, slots=True)
class NormUtterancePlan:
    """Relation recipe the planner may place on an existing talk future."""

    pattern: NormPattern
    predicate: str
    subject: str
    object: str
    source_basis: str = _UNREFERENCED

    def __post_init__(self) -> None:
        if type(self.pattern) is not NormPattern:
            raise _fail("utterance.pattern", "unknown_pattern")
        if self.predicate not in {"expect", "criticize"}:
            raise _fail("utterance.predicate", "unknown_predicate")
        if self.subject != self.pattern.value:
            raise _fail("utterance.subject", "pattern_mismatch")
        if not isinstance(self.object, str) or not self.object:
            raise _fail("utterance.object", "invalid_type")
        if self.source_basis != _UNREFERENCED:
            raise _fail("utterance.source_basis", "unsupported_basis")


@dataclass(frozen=True, slots=True)
class NormTrustRequest:
    """Private request for the loop to append a trust revision intent."""

    target_id: AgentId
    delta: float = _TRUST_DELTA

    def __post_init__(self) -> None:
        if type(self.target_id) is not AgentId:
            raise _fail("trust_request.target_id", "invalid_type")
        object.__setattr__(
            self,
            "delta",
            _locked_float("trust_request.delta", self.delta, _TRUST_DELTA),
        )


@dataclass(frozen=True, slots=True)
class NormBelief:
    """One owner's expectation. It is not a semantic belief."""

    belief_id: str
    owner_id: AgentId
    pattern: NormPattern
    expectation: NormExpectation
    context: NormContext
    status: NormStatus
    confidence: float
    evidence: tuple[NormEvidenceItem, ...] = ()
    supporters: tuple[AgentId, ...] = ()
    consequences: tuple[NormConsequence, ...] = ()
    counterpart_ids: tuple[AgentId, ...] = ()
    response: NormResponse = NormResponse.IGNORE
    chosen_sanction: NormSanction | None = None
    response_reason: str | None = None
    withhold_until_tick: int | None = None
    withhold_agent_id: AgentId | None = None
    last_utterance_tick: int | None = None
    prior_refusal: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "belief_id", _require_hex_id("belief_id", self.belief_id)
        )
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.pattern) is not NormPattern:
            raise _fail("pattern", "unknown_pattern")
        if type(self.expectation) is not NormExpectation:
            raise _fail("expectation", "unknown_expectation")
        if _EXPECTATION_FOR[self.pattern] is not self.expectation:
            raise _fail("expectation", "pattern_mismatch")
        if type(self.context) is not NormContext:
            raise _fail("context", "invalid_type")
        if self.context.pattern is not self.pattern:
            raise _fail("context.pattern", "pattern_mismatch")
        if type(self.status) is not NormStatus:
            raise _fail("status", "unknown_status")
        if type(self.response) is not NormResponse:
            raise _fail("response", "unknown_response")
        confidence = _finite("confidence", self.confidence)
        quantized = _quantize(confidence)
        if quantized < 0.0 or quantized > 1.0:
            raise _fail("confidence", "out_of_range")
        object.__setattr__(self, "confidence", quantized)
        evidence = _require_tuple("evidence", self.evidence)
        checked_evidence: list[NormEvidenceItem] = []
        seen_ids: set[str] = set()
        for item in evidence:
            if type(item) is not NormEvidenceItem:
                raise _fail("evidence", "invalid_type")
            if item.evidence_id in seen_ids:
                raise _fail("evidence", "duplicate_evidence")
            seen_ids.add(item.evidence_id)
            checked_evidence.append(item)
        if len(checked_evidence) > _MAX_EVIDENCE:
            raise _fail("evidence", "cap_exceeded")
        supporters = _require_tuple("supporters", self.supporters)
        checked_supporters: list[AgentId] = []
        seen_supporters: set[str] = set()
        for agent in supporters:
            if type(agent) is not AgentId:
                raise _fail("supporters", "invalid_type")
            if agent.value in seen_supporters:
                raise _fail("supporters", "duplicate_supporter")
            seen_supporters.add(agent.value)
            checked_supporters.append(agent)
        if len(checked_supporters) > _MAX_SUPPORTERS:
            raise _fail("supporters", "cap_exceeded")
        consequences = _require_tuple("consequences", self.consequences)
        checked_consequences: list[NormConsequence] = []
        for item in consequences:
            if type(item) is not NormConsequence:
                raise _fail("consequences", "invalid_type")
            checked_consequences.append(item)
        counterparts = _require_tuple("counterpart_ids", self.counterpart_ids)
        checked_counterparts: list[AgentId] = []
        for agent in counterparts:
            if type(agent) is not AgentId:
                raise _fail("counterpart_ids", "invalid_type")
            checked_counterparts.append(agent)
        ordered = tuple(sorted(checked_counterparts, key=lambda item: item.value))
        if any(left == right for left, right in itertools.pairwise(ordered)):
            raise _fail("counterpart_ids", "duplicate_counterpart")
        expected_id = norm_belief_id(self.owner_id, self.pattern, ordered)
        if self.belief_id != expected_id:
            raise _fail("belief_id", "id_mismatch")
        if self.chosen_sanction is not None and type(self.chosen_sanction) is not (
            NormSanction
        ):
            raise _fail("chosen_sanction", "unknown_sanction")
        if self.response_reason is not None and self.response_reason not in (
            _NOTICE_REASONS
        ):
            raise _fail("response_reason", "invalid_notice")
        if self.withhold_until_tick is not None:
            object.__setattr__(
                self,
                "withhold_until_tick",
                require_exact_nonneg_int(
                    "NormBelief.withhold_until_tick", self.withhold_until_tick
                ),
            )
        if self.withhold_agent_id is not None and type(self.withhold_agent_id) is not (
            AgentId
        ):
            raise _fail("withhold_agent_id", "invalid_type")
        if self.last_utterance_tick is not None:
            object.__setattr__(
                self,
                "last_utterance_tick",
                require_exact_nonneg_int(
                    "NormBelief.last_utterance_tick", self.last_utterance_tick
                ),
            )
        if type(self.prior_refusal) is not bool:
            raise _fail("prior_refusal", "invalid_type")
        object.__setattr__(self, "evidence", tuple(checked_evidence))
        object.__setattr__(self, "supporters", tuple(checked_supporters))
        object.__setattr__(self, "consequences", tuple(checked_consequences))
        object.__setattr__(self, "counterpart_ids", ordered)

    @property
    def conforming_count(self) -> int:
        return sum(
            1
            for item in self.evidence
            if item.channel is NormEvidenceChannel.CONFORMING
        )


@dataclass(frozen=True, slots=True)
class NormWindow:
    """Open return or spare window. It is ledger state, not a world flag."""

    pattern: NormPattern
    until_tick: int
    giver_id: AgentId | None = None
    receiver_id: AgentId | None = None
    sleeper_id: AgentId | None = None

    def __post_init__(self) -> None:
        if type(self.pattern) is not NormPattern:
            raise _fail("window.pattern", "unknown_pattern")
        object.__setattr__(
            self,
            "until_tick",
            require_exact_nonneg_int("NormWindow.until_tick", self.until_tick),
        )
        for name in ("giver_id", "receiver_id", "sleeper_id"):
            value = getattr(self, name)
            if value is not None and type(value) is not AgentId:
                raise _fail(f"window.{name}", "invalid_type")


@dataclass(frozen=True, slots=True)
class NormExchange:
    """Directed-give memory used to recognize a reciprocal pair."""

    left_id: AgentId
    right_id: AgentId
    directions: tuple[str, ...] = ()
    established: bool = False
    idle_until: int | None = None

    def __post_init__(self) -> None:
        if type(self.left_id) is not AgentId or type(self.right_id) is not AgentId:
            raise _fail("exchange", "invalid_type")
        if self.left_id.value > self.right_id.value:
            raise _fail("exchange", "unsorted_pair")
        if type(self.established) is not bool:
            raise _fail("exchange.established", "invalid_type")
        directions = _require_tuple("exchange.directions", self.directions)
        checked: list[str] = []
        for item in directions:
            if not isinstance(item, str) or ">" not in item:
                raise _fail("exchange.directions", "invalid_type")
            checked.append(item)
        object.__setattr__(self, "directions", tuple(checked))
        if self.idle_until is not None:
            object.__setattr__(
                self,
                "idle_until",
                require_exact_nonneg_int("NormExchange.idle_until", self.idle_until),
            )


@dataclass(frozen=True, slots=True)
class NormLedger:
    """Private expectations for one owner. ``None`` means the mode is off."""

    owner_id: AgentId
    beliefs: tuple[NormBelief, ...] = ()
    windows: tuple[NormWindow, ...] = ()
    exchanges: tuple[NormExchange, ...] = ()
    notices: tuple[str, ...] = ()
    utterance_plans: tuple[NormUtterancePlan, ...] = ()
    trust_requests: tuple[NormTrustRequest, ...] = ()
    policy_version: str = SOCIAL_NORM_POLICY_VERSION

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if self.policy_version != SOCIAL_NORM_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        beliefs = _require_tuple("beliefs", self.beliefs)
        checked: list[NormBelief] = []
        seen: set[str] = set()
        for item in beliefs:
            if type(item) is not NormBelief:
                raise _fail("beliefs", "invalid_type")
            if item.owner_id != self.owner_id:
                raise _fail("beliefs.owner_id", "owner_mismatch")
            if item.belief_id in seen:
                raise _fail("beliefs", "duplicate_belief")
            seen.add(item.belief_id)
            checked.append(item)
        if len(checked) > _MAX_BELIEFS:
            raise _fail("beliefs", "cap_exceeded")
        windows = _require_tuple("windows", self.windows)
        for item in windows:
            if type(item) is not NormWindow:
                raise _fail("windows", "invalid_type")
        exchanges = _require_tuple("exchanges", self.exchanges)
        for item in exchanges:
            if type(item) is not NormExchange:
                raise _fail("exchanges", "invalid_type")
        notices = _require_tuple("notices", self.notices)
        checked_notices: list[str] = []
        for item in notices:
            if not isinstance(item, str) or item not in _NOTICE_REASONS:
                raise _fail("notices", "invalid_notice")
            if item not in checked_notices:
                checked_notices.append(item)
        plans = _require_tuple("utterance_plans", self.utterance_plans)
        for item in plans:
            if type(item) is not NormUtterancePlan:
                raise _fail("utterance_plans", "invalid_type")
        requests = _require_tuple("trust_requests", self.trust_requests)
        for item in requests:
            if type(item) is not NormTrustRequest:
                raise _fail("trust_requests", "invalid_type")
        object.__setattr__(self, "beliefs", tuple(checked))
        object.__setattr__(self, "windows", tuple(windows))
        object.__setattr__(self, "exchanges", tuple(exchanges))
        object.__setattr__(self, "notices", tuple(checked_notices))
        object.__setattr__(self, "utterance_plans", tuple(plans))
        object.__setattr__(self, "trust_requests", tuple(requests))
        _LOG.debug(
            "norm_ledger_constructed owner_id=%s policy_version=%s belief_count=%s",
            self.owner_id.value,
            self.policy_version,
            len(self.beliefs),
        )


@dataclass(frozen=True, slots=True)
class SocialNormPolicy:
    """Locked norm constants. Runner JSON does not carry these weights."""

    version: str = SOCIAL_NORM_POLICY_VERSION
    active_confidence: float = _ACTIVE_CONFIDENCE
    enforce_confidence: float = _ENFORCE_CONFIDENCE
    retire_confidence: float = _RETIRE_CONFIDENCE
    decay: float = _DECAY
    conforming_delta: float = _CONFORMING_DELTA
    violation_delta: float = _VIOLATION_DELTA
    penalty: float = _PENALTY
    conforming_count: int = _CONFORMING_COUNT
    return_window_ticks: int = _RETURN_WINDOW
    spare_window_ticks: int = _SPARE_WINDOW
    utterance_interval: int = _UTTERANCE_INTERVAL
    exclusion_window_ticks: int = _EXCLUSION_WINDOW
    scarcity_quantity: float = _SCARCITY_QUANTITY
    critical_need_ratio: float = _CRITICAL_NEED
    trust_delta: float = _TRUST_DELTA
    max_beliefs: int = _MAX_BELIEFS
    max_evidence: int = _MAX_EVIDENCE
    max_supporters: int = _MAX_SUPPORTERS

    def __post_init__(self) -> None:
        if self.version != SOCIAL_NORM_POLICY_VERSION:
            raise _fail("version", "unsupported_policy")
        floats = (
            ("active_confidence", _ACTIVE_CONFIDENCE),
            ("enforce_confidence", _ENFORCE_CONFIDENCE),
            ("retire_confidence", _RETIRE_CONFIDENCE),
            ("decay", _DECAY),
            ("conforming_delta", _CONFORMING_DELTA),
            ("violation_delta", _VIOLATION_DELTA),
            ("penalty", _PENALTY),
            ("scarcity_quantity", _SCARCITY_QUANTITY),
            ("critical_need_ratio", _CRITICAL_NEED),
            ("trust_delta", _TRUST_DELTA),
        )
        for name, expected in floats:
            object.__setattr__(
                self, name, _locked_float(name, getattr(self, name), expected)
            )
        counts = (
            ("conforming_count", _CONFORMING_COUNT),
            ("return_window_ticks", _RETURN_WINDOW),
            ("spare_window_ticks", _SPARE_WINDOW),
            ("utterance_interval", _UTTERANCE_INTERVAL),
            ("exclusion_window_ticks", _EXCLUSION_WINDOW),
            ("max_beliefs", _MAX_BELIEFS),
            ("max_evidence", _MAX_EVIDENCE),
            ("max_supporters", _MAX_SUPPORTERS),
        )
        for name, expected in counts:
            object.__setattr__(
                self, name, _locked_int(name, getattr(self, name), expected)
            )
        _LOG.debug(
            "norm_policy_constructed owner_id=%s policy_version=%s belief_count=%s",
            "-",
            self.version,
            0,
        )


def default_social_norm_policy() -> SocialNormPolicy:
    """Return the only accepted social-norm policy."""
    return SocialNormPolicy()


def empty_norm_ledger(owner_id: AgentId) -> NormLedger:
    """Ledger with no beliefs. Disabled mode does not call this."""
    return NormLedger(owner_id=owner_id)


def require_owner_social_norms(
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
    if type(ledger) is not NormLedger:
        _LOG.warning(
            "norm_carry_rejected reason=%s",
            "invalid_type",
        )
        raise TypeError(f"{field_name} must be NormLedger")
    if ledger.owner_id != owner_id:
        _LOG.error(
            "norm_validation_failed field=%s reason_code=%s",
            field_name,
            "owner_mismatch",
        )
        _LOG.warning(
            "norm_carry_rejected reason=%s",
            "owner_mismatch",
        )
        raise ValueError(f"{field_name} owner_id mismatch")


@dataclass
class _BeliefDraft:
    pattern: NormPattern
    counterparts: tuple[AgentId, ...]
    confidence: float
    status: NormStatus
    evidence: list[NormEvidenceItem]
    supporters: list[AgentId]
    consequences: list[NormConsequence]
    location_id: EntityId | None
    window_until: int | None
    response: NormResponse = NormResponse.IGNORE
    chosen_sanction: NormSanction | None = None
    response_reason: str | None = None
    withhold_until_tick: int | None = None
    withhold_agent_id: AgentId | None = None
    last_utterance_tick: int | None = None
    prior_refusal: bool = False
    touched: bool = False


@dataclass
class _WindowDraft:
    pattern: NormPattern
    until_tick: int
    giver_id: AgentId | None = None
    receiver_id: AgentId | None = None
    sleeper_id: AgentId | None = None


@dataclass
class _ExchangeDraft:
    left_id: AgentId
    right_id: AgentId
    directions: set[str] = field(default_factory=set)
    established: bool = False
    idle_until: int | None = None
    gave_this_tick: bool = False


@dataclass(frozen=True, slots=True)
class NormResponseResult:
    """Penalties plus the ledger after response selection."""

    ledger: NormLedger | None
    penalties: tuple[tuple[str, float], ...] = ()

    def as_dict(self) -> dict[str, float]:
        mapped = dict(self.penalties)
        for value in mapped.values():
            if value < 0.0:
                raise _fail("penalty", "negative_penalty")
        return mapped


def norm_communicate_utterance(
    command: object,
    *,
    owner_id: AgentId,
    tick: int,
    observation: Observation,
    identity: OwnerSafeSocialIdentity | None,
    ledger: object | None,
    mode: object | None,
) -> object:
    """Stamp an existing Talk command with one norm relation recipe."""
    from agents.cognition.configuration import CognitionSocialNormMode
    from world.actions import Talk
    from world.communications import (
        CommunicationRelation,
        CommunicationSourceBasis,
        origin_utterance,
    )

    if mode is not CognitionSocialNormMode.DETERMINISTIC:
        return command
    if type(observation) is not Observation:
        return command
    if type(command) is not Talk:
        return command
    if type(ledger) is not NormLedger or not ledger.utterance_plans:
        return command
    if identity is None:
        return command
    if observation.tick != tick:
        _LOG.warning("norm_communicate_utterance reason=%s", "tick_mismatch")
        return command
    plan = ledger.utterance_plans[0]
    utterance = origin_utterance(
        text=plan.predicate,
        speaker_id=identity.owner_entity_id,
        communication_id=(
            f"social-norms-{owner_id.value}-{tick}-{plan.pattern.value}"
        ),
        relations=(
            CommunicationRelation(
                subject=plan.subject,
                predicate=plan.predicate,
                object=plan.object,
            ),
        ),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    _LOG.debug(
        "norm_communicate_utterance owner_id=%s predicate=%s pattern=%s",
        owner_id.value,
        plan.predicate,
        plan.pattern.value,
    )
    return Talk(recipient_id=command.recipient_id, utterance=utterance)


def _lineage(tick: int, ordinal: int, occurrence: ObservedOccurrence) -> str:
    event_id = occurrence.provenance.source_event_id
    if event_id is None:
        return f"tick-{tick}-{ordinal}"
    return event_id.value


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


def _pair_key(left: AgentId, right: AgentId) -> tuple[AgentId, AgentId]:
    if left.value <= right.value:
        return (left, right)
    return (right, left)


def _direction_token(giver: AgentId, receiver: AgentId) -> str:
    return f"{giver.value}>{receiver.value}"


def _notice(notices: list[str], reason: str) -> None:
    if reason not in notices:
        notices.append(reason)


def _log_drop(reason: str) -> None:
    _LOG.warning("norm_evidence_dropped reason=%s", reason)


def _drafts_from(
    previous: NormLedger | None, owner_id: AgentId
) -> tuple[
    list[_BeliefDraft],
    list[_WindowDraft],
    list[_ExchangeDraft],
]:
    beliefs: list[_BeliefDraft] = []
    windows: list[_WindowDraft] = []
    exchanges: list[_ExchangeDraft] = []
    if previous is None:
        return beliefs, windows, exchanges
    if previous.owner_id != owner_id:
        _LOG.error(
            "norm_validation_failed field=%s reason_code=%s",
            "owner_id",
            "owner_mismatch",
        )
        raise ValueError("owner_id: owner_mismatch")
    for belief in previous.beliefs:
        beliefs.append(
            _BeliefDraft(
                pattern=belief.pattern,
                counterparts=belief.counterpart_ids,
                confidence=belief.confidence,
                status=belief.status,
                evidence=list(belief.evidence),
                supporters=list(belief.supporters),
                consequences=list(belief.consequences),
                location_id=belief.context.location_id,
                window_until=belief.context.window_until_tick,
                response=belief.response,
                chosen_sanction=belief.chosen_sanction,
                response_reason=belief.response_reason,
                withhold_until_tick=belief.withhold_until_tick,
                withhold_agent_id=belief.withhold_agent_id,
                last_utterance_tick=belief.last_utterance_tick,
                prior_refusal=belief.prior_refusal,
            )
        )
    for window in previous.windows:
        windows.append(
            _WindowDraft(
                pattern=window.pattern,
                until_tick=window.until_tick,
                giver_id=window.giver_id,
                receiver_id=window.receiver_id,
                sleeper_id=window.sleeper_id,
            )
        )
    for exchange in previous.exchanges:
        exchanges.append(
            _ExchangeDraft(
                left_id=exchange.left_id,
                right_id=exchange.right_id,
                directions=set(exchange.directions),
                established=exchange.established,
                idle_until=exchange.idle_until,
            )
        )
    return beliefs, windows, exchanges


def _find_belief(
    beliefs: list[_BeliefDraft],
    pattern: NormPattern,
    counterparts: tuple[AgentId, ...],
) -> _BeliefDraft | None:
    key = tuple(sorted(agent.value for agent in counterparts))
    for belief in beliefs:
        if belief.pattern is not pattern:
            continue
        if tuple(sorted(agent.value for agent in belief.counterparts)) == key:
            return belief
    return None


def _record_evidence(
    *,
    beliefs: list[_BeliefDraft],
    notices: list[str],
    owner_id: AgentId,
    pattern: NormPattern,
    counterparts: tuple[AgentId, ...],
    delta: float,
    channel: NormEvidenceChannel,
    lineage_ref: str,
    tick: int,
    actor_id: AgentId | None,
    location_id: EntityId | None,
    window_until: int | None,
    policy: SocialNormPolicy,
    seen: set[tuple[str, str]],
) -> None:
    dedup = (pattern.value, lineage_ref)
    if dedup in seen:
        return
    seen.add(dedup)
    belief = _find_belief(beliefs, pattern, counterparts)
    if belief is None:
        if len(beliefs) >= policy.max_beliefs:
            _notice(notices, "cap_exceeded")
            _log_drop("cap_exceeded")
            return
        belief = _BeliefDraft(
            pattern=pattern,
            counterparts=tuple(sorted(counterparts, key=lambda item: item.value)),
            confidence=0.0,
            status=NormStatus.CANDIDATE,
            evidence=[],
            supporters=[],
            consequences=[],
            location_id=location_id,
            window_until=window_until,
        )
        beliefs.append(belief)
    if len(belief.evidence) >= policy.max_evidence:
        _notice(notices, "cap_exceeded")
        _log_drop("cap_exceeded")
        return
    before = belief.confidence
    belief.confidence = _apply_delta(before, delta)
    belief_id = norm_belief_id(owner_id, pattern, belief.counterparts)
    ordinal = len(belief.evidence)
    belief.evidence.append(
        NormEvidenceItem(
            evidence_id=norm_evidence_id(belief_id, ordinal, channel, lineage_ref),
            ordinal=ordinal,
            channel=channel,
            lineage_ref=lineage_ref,
            tick=tick,
            actor_id=actor_id,
        )
    )
    belief.touched = True
    if location_id is not None:
        belief.location_id = location_id
    if window_until is not None:
        belief.window_until = window_until
    if (
        channel is NormEvidenceChannel.CONFORMING
        and actor_id is not None
        and all(agent != actor_id for agent in belief.supporters)
    ):
        if len(belief.supporters) >= policy.max_supporters:
            _notice(notices, "cap_exceeded")
            _log_drop("cap_exceeded")
        else:
            belief.supporters.append(actor_id)
    if (
        belief.status is NormStatus.RETIRED
        and channel is NormEvidenceChannel.CONFORMING
    ):
        belief.status = NormStatus.CANDIDATE
    _LOG.debug(
        "norm_belief_applied owner_id=%s tick=%s sign=%s",
        owner_id.value,
        tick,
        _sign(before, belief.confidence),
    )


def _scarce(observation: Observation, policy: SocialNormPolicy) -> EntityId | None:
    body = observation.self_body
    if body is None:
        return None
    for resource in observation.resources:
        if (
            resource.kind is ResourceKind.FOOD
            and resource.quantity <= policy.scarcity_quantity
        ):
            return body.location_id
    return None


def _attacks_targeting(
    occurrences: Sequence[ObservedOccurrence], entity_id: EntityId
) -> bool:
    return any(
        occurrence.kind == "attack" and occurrence.other_entity_id == entity_id
        for occurrence in occurrences
    )


def _ensure_candidate(
    beliefs: list[_BeliefDraft],
    pattern: NormPattern,
    counterparts: tuple[AgentId, ...],
    notices: list[str],
    policy: SocialNormPolicy,
) -> _BeliefDraft | None:
    found = _find_belief(beliefs, pattern, counterparts)
    if found is not None:
        return found
    if len(beliefs) >= policy.max_beliefs:
        _notice(notices, "cap_exceeded")
        _log_drop("cap_exceeded")
        return None
    draft = _BeliefDraft(
        pattern=pattern,
        counterparts=tuple(sorted(counterparts, key=lambda item: item.value)),
        confidence=0.0,
        status=NormStatus.CANDIDATE,
        evidence=[],
        supporters=[],
        consequences=[],
        location_id=None,
        window_until=None,
        touched=True,
    )
    beliefs.append(draft)
    return draft


def _append_consequence(
    belief: _BeliefDraft,
    sanction: NormSanction,
    channel: NormConsequenceChannel,
    tick: int,
    actor_id: AgentId | None,
) -> None:
    for item in belief.consequences:
        if (
            item.sanction is sanction
            and item.channel is channel
            and item.tick == tick
            and item.actor_id == actor_id
        ):
            return
    belief.consequences.append(
        NormConsequence(
            sanction=sanction,
            channel=channel,
            tick=tick,
            actor_id=actor_id,
        )
    )
    belief.touched = True


def _promote(
    beliefs: Sequence[_BeliefDraft],
    owner_id: AgentId,
    tick: int,
    policy: SocialNormPolicy,
) -> None:
    for belief in beliefs:
        if belief.status is not NormStatus.CANDIDATE or not belief.touched:
            continue
        count = sum(
            1
            for item in belief.evidence
            if item.channel is NormEvidenceChannel.CONFORMING
        )
        if (
            count >= policy.conforming_count
            and belief.confidence >= policy.active_confidence
        ):
            belief.status = NormStatus.ACTIVE
            _LOG.debug(
                "norm_belief_promoted owner_id=%s tick=%s status=%s",
                owner_id.value,
                tick,
                belief.status.value,
            )
            continue
        if count < policy.conforming_count:
            reason = "below_count"
        elif belief.confidence < policy.active_confidence:
            reason = "below_confidence"
        else:
            reason = "candidate"
        belief.response_reason = reason
        _LOG.warning("norm_belief_withheld reason=%s", reason)


def _decay(
    beliefs: Sequence[_BeliefDraft],
    owner_id: AgentId,
    tick: int,
    policy: SocialNormPolicy,
) -> None:
    for belief in beliefs:
        if belief.touched or belief.status is NormStatus.RETIRED:
            continue
        before = belief.confidence
        after = _apply_delta(before, -policy.decay)
        belief.confidence = after
        if (
            before + 1e-9 >= policy.retire_confidence
            and after < policy.retire_confidence
        ):
            belief.status = NormStatus.RETIRED
            _LOG.debug(
                "norm_belief_retired owner_id=%s tick=%s status=%s",
                owner_id.value,
                tick,
                belief.status.value,
            )


def _freeze(
    owner_id: AgentId,
    beliefs: Sequence[_BeliefDraft],
    windows: Sequence[_WindowDraft],
    exchanges: Sequence[_ExchangeDraft],
    notices: Sequence[str],
    plans: Sequence[NormUtterancePlan] = (),
    requests: Sequence[NormTrustRequest] = (),
) -> NormLedger:
    frozen_beliefs: list[NormBelief] = []
    for draft in beliefs:
        counterparts = tuple(sorted(draft.counterparts, key=lambda item: item.value))
        context = NormContext(
            pattern=draft.pattern,
            location_id=draft.location_id,
            counterpart_id=counterparts[0] if counterparts else None,
            window_until_tick=draft.window_until,
        )
        frozen_beliefs.append(
            NormBelief(
                belief_id=norm_belief_id(owner_id, draft.pattern, counterparts),
                owner_id=owner_id,
                pattern=draft.pattern,
                expectation=_EXPECTATION_FOR[draft.pattern],
                context=context,
                status=draft.status,
                confidence=draft.confidence,
                evidence=tuple(draft.evidence),
                supporters=tuple(draft.supporters),
                consequences=tuple(draft.consequences),
                counterpart_ids=counterparts,
                response=draft.response,
                chosen_sanction=draft.chosen_sanction,
                response_reason=draft.response_reason,
                withhold_until_tick=draft.withhold_until_tick,
                withhold_agent_id=draft.withhold_agent_id,
                last_utterance_tick=draft.last_utterance_tick,
                prior_refusal=draft.prior_refusal,
            )
        )
    frozen_beliefs.sort(key=lambda item: item.belief_id)
    frozen_windows = tuple(
        NormWindow(
            pattern=item.pattern,
            until_tick=item.until_tick,
            giver_id=item.giver_id,
            receiver_id=item.receiver_id,
            sleeper_id=item.sleeper_id,
        )
        for item in windows
    )
    frozen_exchanges = tuple(
        NormExchange(
            left_id=item.left_id,
            right_id=item.right_id,
            directions=tuple(sorted(item.directions)),
            established=item.established,
            idle_until=item.idle_until,
        )
        for item in exchanges
    )
    return NormLedger(
        owner_id=owner_id,
        beliefs=tuple(frozen_beliefs),
        windows=frozen_windows,
        exchanges=frozen_exchanges,
        notices=tuple(notices),
        utterance_plans=tuple(plans),
        trust_requests=tuple(requests),
    )


def apply_norm_update(
    observation: object,
    identity: object,
    previous: object = None,
    policy: SocialNormPolicy | None = None,
) -> NormLedger:
    """Apply one tick of witnessed evidence for a single owner.

    Disabled callers do not call this function. Passing world authority or a
    metric document raises ``TypeError``.
    """
    _LOG.debug(
        "apply_norm_update owner_id=%s tick=%s",
        getattr(getattr(identity, "owner_id", None), "value", None),
        getattr(observation, "tick", None),
    )
    for value in (observation, identity, previous, policy):
        _reject_forbidden(value)
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if type(identity) is not OwnerSafeSocialIdentity:
        raise TypeError("identity must be OwnerSafeSocialIdentity")
    if previous is not None and type(previous) is not NormLedger:
        raise TypeError("previous must be NormLedger or None")
    active_policy = default_social_norm_policy() if policy is None else policy
    if type(active_policy) is not SocialNormPolicy:
        raise TypeError("policy must be SocialNormPolicy")
    owner_id = identity.owner_id
    tick = observation.tick
    beliefs, windows, exchanges = _drafts_from(previous, owner_id)
    notices: list[str] = []
    seen: set[tuple[str, str]] = set()
    occurrences = tuple(observation.occurrences)
    scarcity_location = _scarce(observation, active_policy)

    for ordinal, occurrence in enumerate(occurrences):
        if not isinstance(occurrence.kind, str) or occurrence.kind not in _KNOWN_KINDS:
            if "ignored_kind" not in notices:
                _notice(notices, "ignored_kind")
                _log_drop("ignored_kind")
            continue
        if occurrence.kind == "give":
            _apply_give(
                occurrence=occurrence,
                ordinal=ordinal,
                tick=tick,
                identity=identity,
                beliefs=beliefs,
                windows=windows,
                exchanges=exchanges,
                notices=notices,
                seen=seen,
                policy=active_policy,
                scarcity_location=scarcity_location,
            )
        elif occurrence.kind == "sleep":
            _apply_sleep(
                occurrence=occurrence,
                ordinal=ordinal,
                tick=tick,
                identity=identity,
                occurrences=occurrences,
                beliefs=beliefs,
                windows=windows,
                notices=notices,
                seen=seen,
                policy=active_policy,
            )
        elif occurrence.kind == "attack":
            _apply_attack(
                occurrence=occurrence,
                ordinal=ordinal,
                tick=tick,
                identity=identity,
                beliefs=beliefs,
                windows=windows,
                notices=notices,
                seen=seen,
                policy=active_policy,
            )

    _expire_windows(
        tick=tick,
        owner_id=owner_id,
        beliefs=beliefs,
        windows=windows,
        notices=notices,
        seen=seen,
        policy=active_policy,
    )
    _expire_exchanges(
        tick=tick,
        owner_id=owner_id,
        beliefs=beliefs,
        exchanges=exchanges,
        notices=notices,
        seen=seen,
        policy=active_policy,
    )
    _witness_consequences(
        observation=observation,
        identity=identity,
        beliefs=beliefs,
        tick=tick,
    )
    _promote(beliefs, owner_id, tick, active_policy)
    ledger = _freeze(owner_id, beliefs, windows, exchanges, notices)
    _LOG.info(
        "norm_belief_updated owner_id=%s belief_count=%s",
        owner_id.value,
        len(ledger.beliefs),
    )
    return ledger


def _apply_give(
    *,
    occurrence: ObservedOccurrence,
    ordinal: int,
    tick: int,
    identity: OwnerSafeSocialIdentity,
    beliefs: list[_BeliefDraft],
    windows: list[_WindowDraft],
    exchanges: list[_ExchangeDraft],
    notices: list[str],
    seen: set[tuple[str, str]],
    policy: SocialNormPolicy,
    scarcity_location: EntityId | None,
) -> None:
    if occurrence.success is False:
        return
    actor = _resolve_agent(identity, occurrence.actor_id)
    other = _resolve_agent(identity, occurrence.other_entity_id)
    lineage = _lineage(tick, ordinal, occurrence)
    if actor is None or other is None or actor == other:
        _notice(notices, "unresolved_entity")
        _log_drop("unresolved_entity")
        return
    closed = False
    remaining: list[_WindowDraft] = []
    for window in windows:
        opposite = (
            window.pattern is NormPattern.RETURN_TRANSFER
            and window.giver_id == other
            and window.receiver_id == actor
            and tick <= window.until_tick
        )
        if opposite and not closed:
            closed = True
            _record_evidence(
                beliefs=beliefs,
                notices=notices,
                owner_id=identity.owner_id,
                pattern=NormPattern.RETURN_TRANSFER,
                counterparts=(actor, other),
                delta=policy.conforming_delta,
                channel=NormEvidenceChannel.CONFORMING,
                lineage_ref=lineage,
                tick=tick,
                actor_id=actor,
                location_id=None,
                window_until=None,
                policy=policy,
                seen=seen,
            )
            continue
        remaining.append(window)
    windows[:] = remaining
    if not closed:
        already = any(
            window.pattern is NormPattern.RETURN_TRANSFER
            and window.giver_id == actor
            and window.receiver_id == other
            for window in windows
        )
        if not already:
            windows.append(
                _WindowDraft(
                    pattern=NormPattern.RETURN_TRANSFER,
                    until_tick=tick + policy.return_window_ticks,
                    giver_id=actor,
                    receiver_id=other,
                )
            )
    if scarcity_location is not None:
        _record_evidence(
            beliefs=beliefs,
            notices=notices,
            owner_id=identity.owner_id,
            pattern=NormPattern.SHARE_UNDER_SCARCITY,
            counterparts=(),
            delta=policy.conforming_delta,
            channel=NormEvidenceChannel.CONFORMING,
            lineage_ref=lineage,
            tick=tick,
            actor_id=actor,
            location_id=scarcity_location,
            window_until=None,
            policy=policy,
            seen=seen,
        )
    _apply_exchange(
        actor=actor,
        other=other,
        lineage=lineage,
        tick=tick,
        identity=identity,
        beliefs=beliefs,
        exchanges=exchanges,
        notices=notices,
        seen=seen,
        policy=policy,
    )


def _exchange_for(
    exchanges: list[_ExchangeDraft], left: AgentId, right: AgentId
) -> _ExchangeDraft:
    for item in exchanges:
        if item.left_id == left and item.right_id == right:
            return item
    created = _ExchangeDraft(left_id=left, right_id=right)
    exchanges.append(created)
    return created


def _apply_exchange(
    *,
    actor: AgentId,
    other: AgentId,
    lineage: str,
    tick: int,
    identity: OwnerSafeSocialIdentity,
    beliefs: list[_BeliefDraft],
    exchanges: list[_ExchangeDraft],
    notices: list[str],
    seen: set[tuple[str, str]],
    policy: SocialNormPolicy,
) -> None:
    left, right = _pair_key(actor, other)
    state = _exchange_for(exchanges, left, right)
    token = _direction_token(actor, other)
    state.gave_this_tick = True
    if not state.established:
        state.directions.add(token)
        forward = _direction_token(left, right)
        backward = _direction_token(right, left)
        if forward in state.directions and backward in state.directions:
            state.established = True
            state.idle_until = tick + policy.return_window_ticks
            _ensure_candidate(
                beliefs,
                NormPattern.RECIPROCAL_EXCHANGE,
                (left, right),
                notices,
                policy,
            )
        return
    state.idle_until = tick + policy.return_window_ticks
    _record_evidence(
        beliefs=beliefs,
        notices=notices,
        owner_id=identity.owner_id,
        pattern=NormPattern.RECIPROCAL_EXCHANGE,
        counterparts=(left, right),
        delta=policy.conforming_delta,
        channel=NormEvidenceChannel.CONFORMING,
        lineage_ref=lineage,
        tick=tick,
        actor_id=actor,
        location_id=None,
        window_until=state.idle_until,
        policy=policy,
        seen=seen,
    )


def _apply_sleep(
    *,
    occurrence: ObservedOccurrence,
    ordinal: int,
    tick: int,
    identity: OwnerSafeSocialIdentity,
    occurrences: Sequence[ObservedOccurrence],
    beliefs: list[_BeliefDraft],
    windows: list[_WindowDraft],
    notices: list[str],
    seen: set[tuple[str, str]],
    policy: SocialNormPolicy,
) -> None:
    sleeper_entity = occurrence.actor_id
    sleeper = _resolve_agent(identity, sleeper_entity)
    if sleeper is None or type(sleeper_entity) is not EntityId:
        _notice(notices, "unresolved_entity")
        _log_drop("unresolved_entity")
        return
    if _attacks_targeting(occurrences, sleeper_entity):
        return
    lineage = _lineage(tick, ordinal, occurrence)
    until = tick + policy.spare_window_ticks
    _record_evidence(
        beliefs=beliefs,
        notices=notices,
        owner_id=identity.owner_id,
        pattern=NormPattern.SPARE_AFTER_SLEEP,
        counterparts=(sleeper,),
        delta=policy.conforming_delta,
        channel=NormEvidenceChannel.CONFORMING,
        lineage_ref=lineage,
        tick=tick,
        actor_id=sleeper,
        location_id=None,
        window_until=until,
        policy=policy,
        seen=seen,
    )
    windows.append(
        _WindowDraft(
            pattern=NormPattern.SPARE_AFTER_SLEEP,
            until_tick=until,
            sleeper_id=sleeper,
        )
    )


def _apply_attack(
    *,
    occurrence: ObservedOccurrence,
    ordinal: int,
    tick: int,
    identity: OwnerSafeSocialIdentity,
    beliefs: list[_BeliefDraft],
    windows: list[_WindowDraft],
    notices: list[str],
    seen: set[tuple[str, str]],
    policy: SocialNormPolicy,
) -> None:
    target = _resolve_agent(identity, occurrence.other_entity_id)
    attacker = _resolve_agent(identity, occurrence.actor_id)
    if target is None:
        _notice(notices, "unresolved_entity")
        _log_drop("unresolved_entity")
        return
    lineage = _lineage(tick, ordinal, occurrence)
    remaining: list[_WindowDraft] = []
    violated = False
    for window in windows:
        inside = (
            window.pattern is NormPattern.SPARE_AFTER_SLEEP
            and window.sleeper_id == target
            and tick <= window.until_tick
        )
        if inside and not violated:
            violated = True
            _record_evidence(
                beliefs=beliefs,
                notices=notices,
                owner_id=identity.owner_id,
                pattern=NormPattern.SPARE_AFTER_SLEEP,
                counterparts=(target,),
                delta=policy.violation_delta,
                channel=NormEvidenceChannel.VIOLATION,
                lineage_ref=lineage,
                tick=tick,
                actor_id=attacker,
                location_id=None,
                window_until=None,
                policy=policy,
                seen=seen,
            )
            continue
        remaining.append(window)
    windows[:] = remaining


def _expire_windows(
    *,
    tick: int,
    owner_id: AgentId,
    beliefs: list[_BeliefDraft],
    windows: list[_WindowDraft],
    notices: list[str],
    seen: set[tuple[str, str]],
    policy: SocialNormPolicy,
) -> None:
    remaining: list[_WindowDraft] = []
    for window in windows:
        if tick < window.until_tick:
            remaining.append(window)
            continue
        if (
            window.pattern is NormPattern.RETURN_TRANSFER
            and window.receiver_id is not None
        ):
            counterparts: tuple[AgentId, ...] = ()
            if window.giver_id is not None and window.receiver_id is not None:
                counterparts = (window.giver_id, window.receiver_id)
            giver = "-" if window.giver_id is None else window.giver_id.value
            receiver = window.receiver_id.value
            _record_evidence(
                beliefs=beliefs,
                notices=notices,
                owner_id=owner_id,
                pattern=NormPattern.RETURN_TRANSFER,
                counterparts=counterparts,
                delta=policy.violation_delta,
                channel=NormEvidenceChannel.VIOLATION,
                lineage_ref=f"tick-{tick}-return-{giver}-{receiver}",
                tick=tick,
                actor_id=window.receiver_id,
                location_id=None,
                window_until=None,
                policy=policy,
                seen=seen,
            )
            continue
        if (
            window.pattern is NormPattern.SPARE_AFTER_SLEEP
            and tick >= window.until_tick
        ):
            continue
        remaining.append(window)
    windows[:] = remaining


def _expire_exchanges(
    *,
    tick: int,
    owner_id: AgentId,
    beliefs: list[_BeliefDraft],
    exchanges: list[_ExchangeDraft],
    notices: list[str],
    seen: set[tuple[str, str]],
    policy: SocialNormPolicy,
) -> None:
    for state in exchanges:
        if not state.established or state.gave_this_tick:
            continue
        if state.idle_until is None or tick < state.idle_until:
            continue
        _record_evidence(
            beliefs=beliefs,
            notices=notices,
            owner_id=owner_id,
            pattern=NormPattern.RECIPROCAL_EXCHANGE,
            counterparts=(state.left_id, state.right_id),
            delta=policy.violation_delta,
            channel=NormEvidenceChannel.VIOLATION,
            lineage_ref=f"tick-{tick}-idle-{state.left_id.value}-{state.right_id.value}",
            tick=tick,
            actor_id=None,
            location_id=None,
            window_until=tick + policy.return_window_ticks,
            policy=policy,
            seen=seen,
        )
        state.idle_until = tick + policy.return_window_ticks


def _witness_consequences(
    *,
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    beliefs: list[_BeliefDraft],
    tick: int,
) -> None:
    for communication in observation.communications:
        if type(communication) is not ObservedCommunication:
            continue
        if communication.action_kind not in {"talk", "ask", "tell"}:
            continue
        relations = getattr(getattr(communication, "utterance", None), "content", None)
        relation_items = (
            () if relations is None else getattr(relations, "relations", ())
        )
        speaker = _resolve_agent(identity, communication.speaker_id)
        for relation in relation_items:
            predicate = getattr(relation, "predicate", None)
            obj = getattr(relation, "object", None)
            if predicate != "criticize" or obj not in _PATTERN_TOKENS:
                continue
            pattern = NormPattern(obj)
            for belief in beliefs:
                if belief.pattern is pattern:
                    _append_consequence(
                        belief,
                        NormSanction.CRITICISM,
                        NormConsequenceChannel.WITNESSED,
                        tick,
                        speaker,
                    )
    recent_violators: set[str] = set()
    for belief in beliefs:
        for item in belief.evidence:
            if item.channel is not NormEvidenceChannel.VIOLATION:
                continue
            if item.actor_id is None:
                continue
            if tick - item.tick <= _RETALIATION_LOOKBACK:
                recent_violators.add(item.actor_id.value)
    for occurrence in observation.occurrences:
        if occurrence.kind != "attack":
            continue
        target = _resolve_agent(identity, occurrence.other_entity_id)
        attacker = _resolve_agent(identity, occurrence.actor_id)
        if target is None or target.value not in recent_violators:
            continue
        for belief in beliefs:
            if any(
                item.channel is NormEvidenceChannel.VIOLATION
                and item.actor_id == target
                and tick - item.tick <= _RETALIATION_LOOKBACK
                for item in belief.evidence
            ):
                _append_consequence(
                    belief,
                    NormSanction.RETALIATION,
                    NormConsequenceChannel.WITNESSED,
                    tick,
                    attacker,
                )


def _direction_value(future: object) -> str | None:
    direction = getattr(future, "direction", None)
    if type(direction) is ActionDirection:
        return direction.value
    value = getattr(direction, "value", None)
    if isinstance(value, str):
        return value
    return None


def _future_id(future: object) -> str | None:
    value = getattr(future, "future_id", None)
    if isinstance(value, str) and value:
        return value
    return None


def _targets(
    future: object, agent_id: AgentId, identity: OwnerSafeSocialIdentity | None
) -> bool:
    target_agent = getattr(future, "target_agent_id", None)
    if target_agent == agent_id:
        return True
    target = getattr(future, "target_entity_id", None)
    if identity is None or not isinstance(target, str):
        return False
    entity = None
    try:
        entity = EntityId(target)
    except (TypeError, ValueError):
        return False
    return _resolve_agent(identity, entity) == agent_id


def _has_profile(
    relationships: Sequence[object] | None, owner_id: AgentId, target_id: AgentId
) -> bool:
    if relationships is None:
        return False
    for profile in relationships:
        if (
            getattr(profile, "source_id", None) == owner_id
            and getattr(profile, "target_id", None) == target_id
        ):
            return True
    return False


def _utterance_object(belief: _BeliefDraft, owner_id: AgentId) -> str:
    others = [agent for agent in belief.counterparts if agent != owner_id]
    if others:
        return min(others, key=lambda item: item.value).value
    if belief.counterparts:
        return min(belief.counterparts, key=lambda item: item.value).value
    return _LOCATION_OBJECT


def _add_penalty(penalties: dict[str, float], future_id: str, amount: float) -> None:
    if amount < 0.0 or not math.isfinite(amount):
        raise _fail("penalty", "negative_penalty")
    total = _quantize(penalties.get(future_id, 0.0) + amount)
    if total < 0.0:
        raise _fail("penalty", "negative_penalty")
    penalties[future_id] = total


def _critical(hunger: float, thirst: float, policy: SocialNormPolicy) -> bool:
    return (
        hunger / 100.0 >= policy.critical_need_ratio
        or thirst / 100.0 >= policy.critical_need_ratio
    )


def _select_responses(
    *,
    beliefs: list[_BeliefDraft],
    observation: Observation,
    futures: Sequence[object],
    hunger: float,
    thirst: float,
    identity: OwnerSafeSocialIdentity | None,
    relationships: Sequence[object] | None,
    policy: SocialNormPolicy,
    notices: list[str],
    owner_id: AgentId,
) -> tuple[dict[str, float], list[NormUtterancePlan], list[NormTrustRequest]]:
    penalties: dict[str, float] = {}
    plans: list[NormUtterancePlan] = []
    requests: list[NormTrustRequest] = []
    tick = observation.tick
    scarcity = _scarce(observation, policy) is not None
    for belief in beliefs:
        if belief.status is NormStatus.CANDIDATE:
            belief.response = NormResponse.IGNORE
            belief.response_reason = "candidate_only"
            _LOG.warning("norm_response_withheld reason=%s", "candidate_only")
            continue
        if belief.status is not NormStatus.ACTIVE:
            belief.response = NormResponse.IGNORE
            continue
        violator = _violator(belief, tick, owner_id)
        response, reason = _choose_response(
            belief=belief,
            tick=tick,
            futures=futures,
            hunger=hunger,
            thirst=thirst,
            violator=violator,
            policy=policy,
            scarcity=scarcity,
        )
        belief.response = response
        belief.response_reason = reason
        _LOG.debug(
            "norm_response_selected owner_id=%s tick=%s response=%s",
            owner_id.value,
            tick,
            response.value,
        )
        if reason is not None and response is NormResponse.IGNORE:
            _LOG.warning("norm_response_withheld reason=%s", reason)
        _apply_response_effect(
            belief=belief,
            response=response,
            reason=reason,
            tick=tick,
            futures=futures,
            identity=identity,
            relationships=relationships,
            policy=policy,
            penalties=penalties,
            plans=plans,
            requests=requests,
            notices=notices,
            owner_id=owner_id,
            violator=violator,
            scarcity=scarcity,
            hunger=hunger,
        )
        _apply_withhold(
            belief=belief,
            tick=tick,
            futures=futures,
            identity=identity,
            policy=policy,
            penalties=penalties,
        )
    return penalties, plans, requests


def _violator(belief: _BeliefDraft, tick: int, owner_id: AgentId) -> AgentId | None:
    for item in belief.evidence:
        if (
            item.channel is NormEvidenceChannel.VIOLATION
            and item.tick == tick
            and item.actor_id is not None
            and item.actor_id != owner_id
        ):
            return item.actor_id
    return None


def _has_direction(futures: Sequence[object], value: str) -> bool:
    return any(_direction_value(future) == value for future in futures)


def _choose_response(
    *,
    belief: _BeliefDraft,
    tick: int,
    futures: Sequence[object],
    hunger: float,
    thirst: float,
    violator: AgentId | None,
    policy: SocialNormPolicy,
    scarcity: bool,
) -> tuple[NormResponse, str | None]:
    if violator is not None and belief.confidence + 1e-9 >= policy.enforce_confidence:
        return NormResponse.ENFORCE, None
    uttered = (
        belief.last_utterance_tick is not None
        and tick - belief.last_utterance_tick < policy.utterance_interval
    )
    if belief.confidence + 1e-9 >= policy.active_confidence and _has_direction(
        futures, ActionDirection.COMMUNICATE.value
    ):
        if uttered:
            _LOG.warning("norm_response_withheld reason=%s", "utterance_interval")
        else:
            return NormResponse.COMMUNICATE, None
    if (
        belief.pattern is NormPattern.SHARE_UNDER_SCARCITY
        and scarcity
        and _critical(hunger, thirst, policy)
        and _has_direction(futures, ActionDirection.EAT.value)
    ):
        return NormResponse.VIOLATE, None
    if belief.confidence + 1e-9 >= policy.active_confidence and _matches_expectation(
        belief, futures
    ):
        return NormResponse.FOLLOW, None
    if belief.confidence + 1e-9 >= policy.active_confidence:
        return NormResponse.IGNORE, "no_candidate"
    return NormResponse.IGNORE, None


def _matches_expectation(belief: _BeliefDraft, futures: Sequence[object]) -> bool:
    expectation = _EXPECTATION_FOR[belief.pattern]
    if expectation is NormExpectation.WITHHOLD_ATTACK:
        return any(_direction_value(future) != "attack" for future in futures)
    if expectation in {
        NormExpectation.GIVE,
        NormExpectation.GIVE_BACK,
        NormExpectation.GIVE_AGAIN,
    }:
        return any(_direction_value(future) == "give" for future in futures)
    return False


def _apply_response_effect(
    *,
    belief: _BeliefDraft,
    response: NormResponse,
    reason: str | None,
    tick: int,
    futures: Sequence[object],
    identity: OwnerSafeSocialIdentity | None,
    relationships: Sequence[object] | None,
    policy: SocialNormPolicy,
    penalties: dict[str, float],
    plans: list[NormUtterancePlan],
    requests: list[NormTrustRequest],
    notices: list[str],
    owner_id: AgentId,
    violator: AgentId | None,
    scarcity: bool,
    hunger: float,
) -> None:
    if response is NormResponse.FOLLOW:
        _penalize_contradictions(
            belief=belief,
            futures=futures,
            identity=identity,
            policy=policy,
            penalties=penalties,
            scarcity=scarcity,
            hunger=hunger,
            tick=tick,
        )
        return
    if response is NormResponse.COMMUNICATE:
        _prefer_direction(futures, ActionDirection.COMMUNICATE.value, policy, penalties)
        plans.append(
            NormUtterancePlan(
                pattern=belief.pattern,
                predicate="expect",
                subject=belief.pattern.value,
                object=_utterance_object(belief, owner_id),
            )
        )
        belief.last_utterance_tick = tick
        return
    if response is NormResponse.VIOLATE:
        _prefer_direction(futures, ActionDirection.EAT.value, policy, penalties)
        return
    if response is NormResponse.ENFORCE and violator is not None:
        _enforce(
            belief=belief,
            tick=tick,
            futures=futures,
            identity=identity,
            relationships=relationships,
            policy=policy,
            penalties=penalties,
            plans=plans,
            requests=requests,
            notices=notices,
            owner_id=owner_id,
            violator=violator,
        )
        return
    if reason == "no_candidate":
        _notice(notices, "no_candidate")


def _prefer_direction(
    futures: Sequence[object],
    preferred: str,
    policy: SocialNormPolicy,
    penalties: dict[str, float],
) -> None:
    for future in futures:
        future_id = _future_id(future)
        if future_id is None or _direction_value(future) == preferred:
            continue
        _add_penalty(penalties, future_id, policy.penalty)


def _penalize_contradictions(
    *,
    belief: _BeliefDraft,
    futures: Sequence[object],
    identity: OwnerSafeSocialIdentity | None,
    policy: SocialNormPolicy,
    penalties: dict[str, float],
    scarcity: bool,
    hunger: float,
    tick: int,
) -> None:
    spare_open = belief.pattern is NormPattern.SPARE_AFTER_SLEEP and (
        belief.window_until is not None and tick <= belief.window_until
    )
    for future in futures:
        future_id = _future_id(future)
        if future_id is None:
            continue
        direction = _direction_value(future)
        if (
            spare_open
            and direction == ActionDirection.ATTACK.value
            and belief.counterparts
            and _targets(future, belief.counterparts[0], identity)
        ):
            _add_penalty(penalties, future_id, policy.penalty)
        if (
            belief.pattern is NormPattern.SHARE_UNDER_SCARCITY
            and scarcity
            and hunger / 100.0 < policy.critical_need_ratio
            and direction == ActionDirection.EAT.value
        ):
            _add_penalty(penalties, future_id, policy.penalty)


def _record_sanction(
    belief: _BeliefDraft,
    sanction: NormSanction,
    tick: int,
    owner_id: AgentId,
) -> None:
    belief.chosen_sanction = sanction
    belief.response_reason = None
    _append_consequence(
        belief,
        sanction,
        NormConsequenceChannel.OWN_ACT,
        tick,
        owner_id,
    )
    _LOG.debug(
        "norm_sanction_applied owner_id=%s tick=%s sanction=%s",
        owner_id.value,
        tick,
        sanction.value,
    )


def _enforce(
    *,
    belief: _BeliefDraft,
    tick: int,
    futures: Sequence[object],
    identity: OwnerSafeSocialIdentity | None,
    relationships: Sequence[object] | None,
    policy: SocialNormPolicy,
    penalties: dict[str, float],
    plans: list[NormUtterancePlan],
    requests: list[NormTrustRequest],
    notices: list[str],
    owner_id: AgentId,
    violator: AgentId,
) -> None:
    if _has_direction(futures, ActionDirection.COMMUNICATE.value):
        _prefer_direction(futures, ActionDirection.COMMUNICATE.value, policy, penalties)
        plans.append(
            NormUtterancePlan(
                pattern=belief.pattern,
                predicate="criticize",
                subject=belief.pattern.value,
                object=_utterance_object(belief, owner_id),
            )
        )
        belief.chosen_sanction = NormSanction.CRITICISM
        belief.last_utterance_tick = tick
        _append_consequence(
            belief,
            NormSanction.CRITICISM,
            NormConsequenceChannel.OWN_ACT,
            tick,
            owner_id,
        )
        _LOG.debug(
            "norm_sanction_applied owner_id=%s tick=%s sanction=%s",
            owner_id.value,
            tick,
            NormSanction.CRITICISM.value,
        )
        return
    help_or_give = [
        future
        for future in futures
        if _direction_value(future) in {ActionDirection.HELP.value, "give"}
        and _targets(future, violator, identity)
    ]
    if help_or_give:
        for future in help_or_give:
            future_id = _future_id(future)
            if future_id is not None:
                _add_penalty(penalties, future_id, policy.penalty)
        _record_sanction(
            belief,
            NormSanction.REFUSAL,
            tick,
            owner_id,
        )
        belief.prior_refusal = True
        return
    if _has_profile(relationships, owner_id, violator):
        requests.append(NormTrustRequest(target_id=violator))
        _record_sanction(
            belief,
            NormSanction.REDUCED_TRUST,
            tick,
            owner_id,
        )
        return
    witnessed_retaliation = any(
        item.sanction is NormSanction.RETALIATION
        and item.channel is NormConsequenceChannel.WITNESSED
        for item in belief.consequences
    )
    attack = [
        future
        for future in futures
        if _direction_value(future) == ActionDirection.ATTACK.value
        and _targets(future, violator, identity)
    ]
    if witnessed_retaliation and attack:
        for future in futures:
            future_id = _future_id(future)
            if future_id is None or future in attack:
                continue
            _add_penalty(penalties, future_id, policy.penalty)
        _record_sanction(
            belief,
            NormSanction.RETALIATION,
            tick,
            owner_id,
        )
        return
    own_exclusion = any(
        item.sanction is NormSanction.EXCLUSION
        and item.channel is NormConsequenceChannel.OWN_ACT
        for item in belief.consequences
    )
    if own_exclusion or belief.prior_refusal:
        belief.withhold_until_tick = tick + policy.exclusion_window_ticks
        belief.withhold_agent_id = violator
        _record_sanction(
            belief,
            NormSanction.EXCLUSION,
            tick,
            owner_id,
        )
        return
    if not _has_profile(relationships, owner_id, violator):
        _LOG.warning("trust_revision_skipped reason=%s", "no_profile")
        _notice(notices, "no_profile")
    if witnessed_retaliation or not attack:
        belief.response_reason = "sanction_unavailable"
        _notice(notices, "sanction_unavailable")
        _LOG.warning("norm_sanction_skipped reason=%s", "sanction_unavailable")
        return
    belief.response_reason = "sanction_latent"
    _notice(notices, "sanction_latent")
    _LOG.warning("norm_sanction_skipped reason=%s", "sanction_latent")


def _apply_withhold(
    *,
    belief: _BeliefDraft,
    tick: int,
    futures: Sequence[object],
    identity: OwnerSafeSocialIdentity | None,
    policy: SocialNormPolicy,
    penalties: dict[str, float],
) -> None:
    agent = belief.withhold_agent_id
    until = belief.withhold_until_tick
    if agent is None or until is None or tick > until:
        return
    for future in futures:
        direction = _direction_value(future)
        if direction not in {
            ActionDirection.HELP.value,
            "give",
            ActionDirection.COMMUNICATE.value,
        }:
            continue
        if not _targets(future, agent, identity):
            continue
        future_id = _future_id(future)
        if future_id is not None:
            _add_penalty(penalties, future_id, policy.penalty)


def norm_response_penalties(
    ledger: object,
    observation: object,
    futures: Sequence[object],
    hunger: float,
    thirst: float,
    *,
    identity: OwnerSafeSocialIdentity | None = None,
    relationships: Sequence[object] | None = None,
    mode: object | None = None,
    policy: SocialNormPolicy | None = None,
) -> NormResponseResult:
    """Penalize futures the planner already has. Does not construct commands."""
    _reject_forbidden(observation)
    _reject_forbidden(ledger)
    if mode is not None:
        from agents.cognition.configuration import CognitionSocialNormMode

        if mode is not CognitionSocialNormMode.DETERMINISTIC:
            return NormResponseResult(ledger=None, penalties=())
    if type(ledger) is not NormLedger:
        return NormResponseResult(ledger=None, penalties=())
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    number_hunger = _finite("hunger", hunger)
    number_thirst = _finite("thirst", thirst)
    active_policy = default_social_norm_policy() if policy is None else policy
    if type(active_policy) is not SocialNormPolicy:
        raise TypeError("policy must be SocialNormPolicy")
    beliefs, windows, exchanges = _drafts_from(ledger, ledger.owner_id)
    notices: list[str] = []
    penalties, plans, requests = _select_responses(
        beliefs=beliefs,
        observation=observation,
        futures=futures,
        hunger=number_hunger,
        thirst=number_thirst,
        identity=identity,
        relationships=relationships,
        policy=active_policy,
        notices=notices,
        owner_id=ledger.owner_id,
    )
    _decay(beliefs, ledger.owner_id, observation.tick, active_policy)
    updated = _freeze(
        ledger.owner_id,
        beliefs,
        windows,
        exchanges,
        notices,
        plans,
        requests,
    )
    ordered = tuple(sorted(penalties.items()))
    return NormResponseResult(ledger=updated, penalties=ordered)
