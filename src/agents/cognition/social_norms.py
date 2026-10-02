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
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Final

from agents.models import AgentId
from world.identifiers import EntityId, require_exact_nonneg_int

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
