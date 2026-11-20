"""Owner-scoped competing scientific explanations.

A competing theory is one owner's fallible account of an observable
regularity. Accounts never carry world authority: they do not create commands,
alter admission, or install objective truth. Social support and predictive
accuracy are independent facts, and no global winner is ever selected.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any, Final

from agents.cognition.scientific_models import (
    SEASON_CLASSES,
    ForecastCase,
    ModelTargetKind,
    target_alphabet,
)
from world.identifiers import AgentId, require_stable_id

__all__ = [
    "MAX_CITATIONS",
    "MAX_CLAIMS",
    "MAX_CLAIMS_PER_BUNDLE",
    "MAX_PENDING_CASES",
    "MAX_RECEIPTS",
    "MAX_STANCES",
    "MAX_TERMINAL_CASES",
    "THEORIES_POLICY_VERSION",
    "THEORY_HORIZON_TICKS",
    "CompetingTheoryLedger",
    "TheoryAccount",
    "TheoryBaseOutcome",
    "TheoryCaseForecast",
    "TheoryCaseOutcome",
    "TheoryCaseState",
    "TheoryCitation",
    "TheoryCitationKind",
    "TheoryCitationPolarity",
    "TheoryClaim",
    "TheoryContext",
    "TheoryCoverage",
    "TheoryForecastCase",
    "TheoryOutboundCorrelation",
    "TheorySenderEcho",
    "TheorySocialKind",
    "TheorySocialReceipt",
    "TheorySpeechAct",
    "TheoryStance",
    "TheoryStanceAction",
    "TheoryStanceRequest",
    "TheoryTargetKind",
    "active_supported_claim",
    "apply_theory_updates",
    "derive_local_theory_claims",
    "empty_competing_theory_ledger",
    "theory_case_id",
    "theory_claim_id",
    "theory_context_digest",
    "theory_context_from_case",
    "unique_citation_roots",
]

THEORIES_POLICY_VERSION: Final[str] = "competing-theories.v1"
THEORY_HORIZON_TICKS: Final[int] = 2

MAX_CLAIMS: Final[int] = 32
MAX_CITATIONS: Final[int] = 256
MAX_STANCES: Final[int] = 128
MAX_RECEIPTS: Final[int] = 256
MAX_TERMINAL_CASES: Final[int] = 256
MAX_PENDING_CASES: Final[int] = 64
MAX_CLAIMS_PER_BUNDLE: Final[int] = 4
MAX_FORECASTS_PER_CASE: Final[int] = MAX_CLAIMS_PER_BUNDLE
MAX_ECHOES: Final[int] = 256
MAX_OUTBOUND: Final[int] = 64
MAX_FOUNDING_CONTEXTS: Final[int] = 64

_CONTINUITY_RESOURCE_CATEGORY: Final[str] = "unchanged"

_COVERAGE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "alphabet_mismatch",
        "base_case_unavailable",
        "case_cap",
        "citation_cap",
        "claim_cap",
        "claim_truncation",
        "duplicate_settle",
        "foreign_owner",
        "horizon_miss",
        "late_settle",
        "no_eligible_claims",
        "not_comparable",
        "pending_cap",
        "receipt_cap",
        "refused_citation",
        "stance_cap",
        "terminal_cap",
        "unsupported_target",
    }
)


def _fail(field_name: str, reason: str) -> ValueError:
    return ValueError(f"{field_name}: {reason}")


def _digest(*parts: str) -> str:
    material = "|".join((THEORIES_POLICY_VERSION, *parts))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _require_text(field_name: str, value: object, *, max_length: int = 128) -> str:
    if not isinstance(value, str) or not value:
        raise _fail(field_name, "invalid_type")
    if len(value) > max_length or value != value.strip():
        raise _fail(field_name, "invalid_value")
    if any(ord(char) < 32 for char in value):
        raise _fail(field_name, "invalid_value")
    return value


def _require_int(
    field_name: str,
    value: object,
    *,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or type(value) is not int:
        raise _fail(field_name, "invalid_type")
    if value < minimum:
        raise _fail(field_name, "invalid_range")
    if maximum is not None and value > maximum:
        raise _fail(field_name, "invalid_range")
    return value


def _require_tuple(field_name: str, value: object) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
        raise _fail(field_name, "invalid_type")
    return value


class TheoryTargetKind(StrEnum):
    """Closed explanatory target domains for this increment."""

    SEASON = "season"
    RESOURCE_REGENERATION = "resource_regeneration"


class TheoryAccount(StrEnum):
    """Two closed explanatory accounts. Neither is a physical law."""

    CONTINUITY = "continuity"
    RECURRENCE = "recurrence"


class TheoryCitationPolarity(StrEnum):
    """How one owner-local fact relates to an explanation."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXT_ONLY = "context_only"


class TheoryCitationKind(StrEnum):
    """Closed provenance kinds for one citation."""

    OWN_OBSERVATION = "own_observation"
    OWN_SCORED_CASE = "own_scored_case"
    DELIVERED_CLAIM = "delivered_claim"
    DECLARED_POINTER = "declared_pointer"


class TheoryStanceAction(StrEnum):
    """Explicit owner stance act. Silence is never opposition."""

    SUPPORT = "support"
    WITHDRAW = "withdraw"


class TheorySocialKind(StrEnum):
    """Closed social receipt kinds."""

    COMMUNICATED = "communicated"
    TAUGHT = "taught"


class TheorySpeechAct(StrEnum):
    """Closed acts carried by one ``thy_v1`` utterance."""

    SHARE = "share"
    SUPPORT = "support"
    WITHDRAW = "withdraw"
    TEACH = "teach"


class TheoryCaseState(StrEnum):
    """Theory-level case lifecycle. Only pending still settles."""

    PENDING = "pending"
    SCORED = "scored"
    NOT_COMPARABLE = "not_comparable"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class TheoryContext:
    """Transferable explanatory context without a local entity binding."""

    target_kind: TheoryTargetKind
    location_id: str
    origin_season: str
    resource_kind: str | None = None
    unit: str | None = None

    def __post_init__(self) -> None:
        if type(self.target_kind) is not TheoryTargetKind:
            raise _fail("target_kind", "invalid_type")
        require_stable_id("location_id", self.location_id)
        if self.origin_season not in SEASON_CLASSES:
            raise _fail("origin_season", "invalid_class")
        if self.target_kind is TheoryTargetKind.SEASON:
            if self.resource_kind is not None or self.unit is not None:
                raise _fail("resource_kind", "unexpected")
        else:
            _require_text("resource_kind", self.resource_kind, max_length=64)
            _require_text("unit", self.unit, max_length=64)

    @property
    def continuity_category(self) -> str:
        """The null account: current season or unchanged resources."""

        if self.target_kind is TheoryTargetKind.SEASON:
            return self.origin_season
        return _CONTINUITY_RESOURCE_CATEGORY


def theory_context_digest(context: TheoryContext) -> str:
    """Stable digest of the transferable context. Entity binding is excluded."""

    if type(context) is not TheoryContext:
        raise _fail("context", "invalid_type")
    return "thctx:" + _digest(
        context.target_kind.value,
        context.location_id,
        context.origin_season,
        context.resource_kind or "",
        context.unit or "",
    )


def theory_claim_id(
    context: TheoryContext, account: TheoryAccount, predicted_category: str
) -> str:
    """Content-addressed explanation identity. Author and support are excluded."""

    if type(context) is not TheoryContext:
        raise _fail("context", "invalid_type")
    if type(account) is not TheoryAccount:
        raise _fail("account", "invalid_type")
    _require_text("predicted_category", predicted_category, max_length=64)
    return "thy-" + _digest(
        context.target_kind.value,
        context.location_id,
        context.origin_season,
        context.resource_kind or "",
        context.unit or "",
        account.value,
        predicted_category,
    )


def theory_case_id(owner_id: AgentId, base_case_id: str) -> str:
    """Stable theory case identity from the owner and the issuing base case."""

    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    require_stable_id("base_case_id", base_case_id)
    return "thc-" + _digest(owner_id.value, base_case_id)


@dataclass(frozen=True, slots=True)
class TheoryClaim:
    """One fallible owner explanation with optional local seed provenance."""

    context: TheoryContext
    account: TheoryAccount
    predicted_category: str
    claim_id: str
    created_tick: int
    sequence: int = 0
    seed_outcome_ref: str = ""
    seed_outcome_tick: int | None = None
    locally_derived_tick: int | None = None

    def __post_init__(self) -> None:
        if type(self.context) is not TheoryContext:
            raise _fail("context", "invalid_type")
        if type(self.account) is not TheoryAccount:
            raise _fail("account", "invalid_type")
        _require_text("predicted_category", self.predicted_category, max_length=64)
        if self.predicted_category not in target_alphabet(
            _model_target_kind(self.context.target_kind)
        ):
            raise _fail("predicted_category", "invalid_class")
        require_stable_id("claim_id", self.claim_id)
        _require_int("created_tick", self.created_tick)
        _require_int("sequence", self.sequence)
        if self.account is TheoryAccount.CONTINUITY:
            if self.predicted_category != self.context.continuity_category:
                raise _fail("predicted_category", "not_continuity")
        else:
            if self.predicted_category == self.context.continuity_category:
                raise _fail("predicted_category", "recurrence_matches_continuity")
        if bool(self.seed_outcome_ref) != (self.seed_outcome_tick is not None):
            raise _fail("seed_outcome_ref", "incomplete_seed")
        if self.seed_outcome_ref:
            require_stable_id("seed_outcome_ref", self.seed_outcome_ref)
        if self.seed_outcome_tick is not None:
            _require_int("seed_outcome_tick", self.seed_outcome_tick)
        if self.locally_derived_tick is not None:
            _require_int("locally_derived_tick", self.locally_derived_tick)

    @property
    def available_tick(self) -> int:
        """First tick at which this claim may enter a frozen case."""

        if self.account is TheoryAccount.RECURRENCE:
            if self.locally_derived_tick is not None:
                return max(self.created_tick, self.locally_derived_tick)
        return self.created_tick

    @property
    def registration_key(self) -> tuple[int, str]:
        return (self.created_tick, self.claim_id)


def _model_target_kind(kind: TheoryTargetKind) -> ModelTargetKind:
    return ModelTargetKind(kind.value)


@dataclass(frozen=True, slots=True)
class TheoryCitation:
    """One attributed owner-local reason to support or contradict a claim."""

    claim_id: str
    owner_tick: int
    polarity: TheoryCitationPolarity
    kind: TheoryCitationKind
    root_ref: str = ""
    provenance_ref: str = ""

    def __post_init__(self) -> None:
        require_stable_id("claim_id", self.claim_id)
        _require_int("owner_tick", self.owner_tick)
        if type(self.polarity) is not TheoryCitationPolarity:
            raise _fail("polarity", "invalid_type")
        if type(self.kind) is not TheoryCitationKind:
            raise _fail("kind", "invalid_type")
        if self.root_ref:
            require_stable_id("root_ref", self.root_ref)
        if self.provenance_ref:
            require_stable_id("provenance_ref", self.provenance_ref)
        if (
            self.kind
            in (
                TheoryCitationKind.OWN_OBSERVATION,
                TheoryCitationKind.OWN_SCORED_CASE,
            )
            and not self.root_ref
        ):
            raise _fail("root_ref", "missing_owned_root")

    @property
    def citation_id(self) -> str:
        return "thcit-" + _digest(
            self.claim_id,
            str(self.owner_tick),
            self.polarity.value,
            self.kind.value,
            self.root_ref,
            self.provenance_ref,
        )

    @property
    def independent_root(self) -> str | None:
        """An owned root is independent; inherited or unknown roots are not."""

        if self.kind in (
            TheoryCitationKind.OWN_OBSERVATION,
            TheoryCitationKind.OWN_SCORED_CASE,
        ):
            return self.root_ref or None
        return None


@dataclass(frozen=True, slots=True)
class TheoryStanceRequest:
    """One explicit local stance act supplied to the pure update."""

    context: TheoryContext
    action: TheoryStanceAction
    claim_id: str | None = None

    def __post_init__(self) -> None:
        if type(self.context) is not TheoryContext:
            raise _fail("context", "invalid_type")
        if type(self.action) is not TheoryStanceAction:
            raise _fail("action", "invalid_type")
        if self.action is TheoryStanceAction.SUPPORT:
            require_stable_id("claim_id", self.claim_id)
        elif self.claim_id is not None:
            require_stable_id("claim_id", self.claim_id)


@dataclass(frozen=True, slots=True)
class TheoryStance:
    """One append-only stance revision. Only the latest row is active."""

    stance_id: str
    context: TheoryContext
    action: TheoryStanceAction
    tick: int
    revision_index: int
    claim_id: str | None = None

    def __post_init__(self) -> None:
        require_stable_id("stance_id", self.stance_id)
        if type(self.context) is not TheoryContext:
            raise _fail("context", "invalid_type")
        if type(self.action) is not TheoryStanceAction:
            raise _fail("action", "invalid_type")
        _require_int("tick", self.tick)
        _require_int("revision_index", self.revision_index)
        if self.action is TheoryStanceAction.SUPPORT:
            require_stable_id("claim_id", self.claim_id)
        elif self.claim_id is not None:
            raise _fail("claim_id", "withdraw_with_claim")


@dataclass(frozen=True, slots=True)
class TheorySocialReceipt:
    """One observed addressed communication or teaching receipt."""

    receipt_id: str
    claim_id: str
    speaker_id: AgentId
    kind: TheorySocialKind
    tick: int
    root_ref: str = ""
    relation_ref: str = ""
    act: TheorySpeechAct = TheorySpeechAct.SHARE
    origin: bool = False

    def __post_init__(self) -> None:
        require_stable_id("receipt_id", self.receipt_id)
        require_stable_id("claim_id", self.claim_id)
        if type(self.speaker_id) is not AgentId:
            raise _fail("speaker_id", "invalid_type")
        if type(self.kind) is not TheorySocialKind:
            raise _fail("kind", "invalid_type")
        _require_int("tick", self.tick)
        if self.root_ref:
            require_stable_id("root_ref", self.root_ref)
        if self.relation_ref:
            require_stable_id("relation_ref", self.relation_ref)
        if type(self.act) is not TheorySpeechAct:
            raise _fail("act", "invalid_type")
        if type(self.origin) is not bool:
            raise _fail("origin", "invalid_type")


@dataclass(frozen=True, slots=True)
class TheorySenderEcho:
    """One sender-observed echo of an outbound theory utterance."""

    echo_id: str
    recipient_entity_id: str
    claim_id: str
    stance_revision: str
    act: TheorySpeechAct
    send_tick: int
    observed_tick: int
    frame_digest: str
    event_ref: str = ""

    def __post_init__(self) -> None:
        require_stable_id("echo_id", self.echo_id)
        require_stable_id("recipient_entity_id", self.recipient_entity_id)
        require_stable_id("claim_id", self.claim_id)
        require_stable_id("stance_revision", self.stance_revision)
        if type(self.act) is not TheorySpeechAct:
            raise _fail("act", "invalid_type")
        _require_int("send_tick", self.send_tick)
        _require_int("observed_tick", self.observed_tick)
        require_stable_id("frame_digest", self.frame_digest)
        if self.event_ref:
            require_stable_id("event_ref", self.event_ref)


@dataclass(frozen=True, slots=True)
class TheoryOutboundCorrelation:
    """Bounded correlation recorded only from the final submitted frame."""

    correlation_id: str
    recipient_entity_id: str
    claim_id: str
    stance_revision: str
    act: TheorySpeechAct
    send_tick: int
    frame_digest: str

    def __post_init__(self) -> None:
        require_stable_id("correlation_id", self.correlation_id)
        require_stable_id("recipient_entity_id", self.recipient_entity_id)
        require_stable_id("claim_id", self.claim_id)
        require_stable_id("stance_revision", self.stance_revision)
        if type(self.act) is not TheorySpeechAct:
            raise _fail("act", "invalid_type")
        _require_int("send_tick", self.send_tick)
        require_stable_id("frame_digest", self.frame_digest)


@dataclass(frozen=True, slots=True)
class TheoryCoverage:
    """Aggregated coverage notice. Repeats increment counts, never append."""

    reason_code: str
    first_tick: int
    last_tick: int
    count: int

    def __post_init__(self) -> None:
        if self.reason_code not in _COVERAGE_REASONS:
            raise _fail("reason_code", "unknown_reason")
        _require_int("first_tick", self.first_tick)
        _require_int("last_tick", self.last_tick)
        _require_int("count", self.count, minimum=1)
        if self.last_tick < self.first_tick:
            raise _fail("last_tick", "before_first_tick")


@dataclass(frozen=True, slots=True)
class TheoryCaseForecast:
    """One frozen theory-level categorical forecast inside a case."""

    claim_id: str
    predicted_category: str
    alphabet: tuple[str, ...]
    probabilities_milli: tuple[int, ...]
    confidence_milli: int
    registration_tick: int

    def __post_init__(self) -> None:
        require_stable_id("claim_id", self.claim_id)
        _require_text("predicted_category", self.predicted_category, max_length=64)
        alphabet = _require_tuple("alphabet", self.alphabet)
        if not alphabet or len(alphabet) > 5:
            raise _fail("alphabet", "invalid_cap")
        if len(set(alphabet)) != len(alphabet):
            raise _fail("alphabet", "duplicate_class")
        probabilities = _require_tuple("probabilities_milli", self.probabilities_milli)
        if len(probabilities) != len(alphabet):
            raise _fail("probabilities_milli", "invalid_alphabet")
        total = 0
        for value in probabilities:
            _require_int("probabilities_milli", value)
            total += value
        if total != 1000:
            raise _fail("probabilities_milli", "invalid_sum")
        if self.predicted_category not in alphabet:
            raise _fail("predicted_category", "invalid_class")
        _require_int("confidence_milli", self.confidence_milli, maximum=1000)
        index = alphabet.index(self.predicted_category)
        if self.confidence_milli != probabilities[index]:
            raise _fail("confidence_milli", "not_predicted_probability")
        if probabilities[index] != max(probabilities):
            raise _fail("predicted_category", "not_argmax")
        _require_int("registration_tick", self.registration_tick)


@dataclass(frozen=True, slots=True)
class TheoryCaseOutcome:
    """One claim's actual scored result inside a settled theory case."""

    claim_id: str
    predicted_category: str
    observed_category: str
    hit: bool
    brier_numerator: int

    def __post_init__(self) -> None:
        require_stable_id("claim_id", self.claim_id)
        _require_text("predicted_category", self.predicted_category, max_length=64)
        _require_text("observed_category", self.observed_category, max_length=64)
        if type(self.hit) is not bool:
            raise _fail("hit", "invalid_type")
        _require_int("brier_numerator", self.brier_numerator, maximum=2_000_000)


@dataclass(frozen=True, slots=True)
class TheoryForecastCase:
    """A frozen same-outcome contest among up to four owner explanations."""

    case_id: str
    owner_id: AgentId
    context: TheoryContext
    base_case_id: str
    alphabet: tuple[str, ...]
    forecasts: tuple[TheoryCaseForecast, ...]
    issued_tick: int
    target_tick: int
    state: TheoryCaseState = TheoryCaseState.PENDING
    observed_category: str | None = None
    outcome_ref: str = ""
    terminal_tick: int | None = None
    settlement_reason: str = ""
    outcomes: tuple[TheoryCaseOutcome, ...] = ()

    def __post_init__(self) -> None:
        require_stable_id("case_id", self.case_id)
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.context) is not TheoryContext:
            raise _fail("context", "invalid_type")
        require_stable_id("base_case_id", self.base_case_id)
        alphabet = _require_tuple("alphabet", self.alphabet)
        if alphabet != target_alphabet(_model_target_kind(self.context.target_kind)):
            raise _fail("alphabet", "invalid_alphabet")
        forecasts = _require_tuple("forecasts", self.forecasts)
        if not forecasts or len(forecasts) > MAX_FORECASTS_PER_CASE:
            raise _fail("forecasts", "invalid_count")
        claim_ids: set[str] = set()
        for forecast in forecasts:
            if type(forecast) is not TheoryCaseForecast:
                raise _fail("forecasts", "invalid_type")
            if forecast.claim_id in claim_ids:
                raise _fail("forecasts", "duplicate_claim")
            claim_ids.add(forecast.claim_id)
            if forecast.alphabet != alphabet:
                raise _fail("forecasts", "invalid_alphabet")
            if forecast.predicted_category not in alphabet:
                raise _fail("forecasts", "invalid_class")
        _require_int("issued_tick", self.issued_tick)
        _require_int("target_tick", self.target_tick)
        if self.target_tick != self.issued_tick + THEORY_HORIZON_TICKS:
            raise _fail("target_tick", "invalid_horizon")
        if type(self.state) is not TheoryCaseState:
            raise _fail("state", "invalid_type")
        outcomes = _require_tuple("outcomes", self.outcomes)
        if self.state is TheoryCaseState.PENDING:
            if (
                self.observed_category is not None
                or outcomes
                or self.terminal_tick is not None
            ):
                raise _fail("state", "pending_with_outcome")
            if self.settlement_reason:
                raise _fail("settlement_reason", "unexpected")
        elif self.state is TheoryCaseState.SCORED:
            if self.observed_category is None or not outcomes:
                raise _fail("state", "scored_without_outcome")
            if self.observed_category not in alphabet:
                raise _fail("observed_category", "invalid_class")
        else:
            if self.observed_category is not None or outcomes:
                raise _fail("state", "unscored_with_outcome")
        if self.terminal_tick is not None:
            _require_int("terminal_tick", self.terminal_tick)
        if self.outcome_ref:
            require_stable_id("outcome_ref", self.outcome_ref)
        if self.settlement_reason:
            _require_text("settlement_reason", self.settlement_reason, max_length=64)
        for row in outcomes:
            if type(row) is not TheoryCaseOutcome:
                raise _fail("outcomes", "invalid_type")
            if row.claim_id not in claim_ids:
                raise _fail("outcomes", "unknown_claim")
            if row.predicted_category not in alphabet or (
                row.observed_category not in alphabet
            ):
                raise _fail("outcomes", "invalid_class")

    @property
    def is_pending(self) -> bool:
        return self.state is TheoryCaseState.PENDING

    @property
    def hit_count(self) -> int:
        return sum(1 for row in self.outcomes if row.hit)

    @property
    def failure_count(self) -> int:
        return sum(1 for row in self.outcomes if not row.hit)


@dataclass(frozen=True, slots=True)
class TheoryBaseOutcome:
    """The exact owner observation that settles one theory case."""

    owner_id: AgentId
    base_case_id: str
    observed_category: str
    observed_tick: int
    outcome_ref: str
    location_id: str
    season: str
    resource_kind: str | None = None
    unit_token: str | None = None

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        require_stable_id("base_case_id", self.base_case_id)
        _require_text("observed_category", self.observed_category, max_length=64)
        _require_int("observed_tick", self.observed_tick)
        require_stable_id("outcome_ref", self.outcome_ref)
        require_stable_id("location_id", self.location_id)
        if self.season not in SEASON_CLASSES:
            raise _fail("season", "invalid_class")
        if self.resource_kind is not None:
            _require_text("resource_kind", self.resource_kind, max_length=64)
        if self.unit_token is not None:
            _require_text("unit_token", self.unit_token, max_length=64)


@dataclass(frozen=True, slots=True)
class CompetingTheoryLedger:
    """Bounded owner-local competing explanations. Outside the objective fold."""

    owner_id: AgentId
    policy_version: str = THEORIES_POLICY_VERSION
    claims: tuple[TheoryClaim, ...] = ()
    citations: tuple[TheoryCitation, ...] = ()
    stances: tuple[TheoryStance, ...] = ()
    receipts: tuple[TheorySocialReceipt, ...] = ()
    cases: tuple[TheoryForecastCase, ...] = ()
    echoes: tuple[TheorySenderEcho, ...] = ()
    outbound: tuple[TheoryOutboundCorrelation, ...] = ()
    founding_consumed: tuple[str, ...] = ()
    coverage: tuple[TheoryCoverage, ...] = ()
    issued_base_case_ids: tuple[str, ...] = ()
    sequence: int = 0
    claim_sequence: int = 0
    stance_sequence: int = 0
    receipt_sequence: int = 0
    case_sequence: int = 0
    refused_claims: int = 0
    refused_citations: int = 0
    refused_stances: int = 0
    refused_receipts: int = 0
    evicted_cases: int = 0
    first_retained_tick: int | None = None
    last_issued_tick: int = -1

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if self.policy_version != THEORIES_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        for name in (
            "claims",
            "citations",
            "stances",
            "receipts",
            "cases",
            "echoes",
            "outbound",
            "founding_consumed",
            "coverage",
            "issued_base_case_ids",
        ):
            _require_tuple(name, getattr(self, name))
        if len(self.claims) > MAX_CLAIMS:
            raise _fail("claims", "cap_exceeded")
        if len(self.citations) > MAX_CITATIONS:
            raise _fail("citations", "cap_exceeded")
        if len(self.stances) > MAX_STANCES:
            raise _fail("stances", "cap_exceeded")
        if len(self.receipts) > MAX_RECEIPTS:
            raise _fail("receipts", "cap_exceeded")
        if len(self.echoes) > MAX_ECHOES:
            raise _fail("echoes", "cap_exceeded")
        if len(self.outbound) > MAX_OUTBOUND:
            raise _fail("outbound", "cap_exceeded")
        if len(self.founding_consumed) > MAX_FOUNDING_CONTEXTS:
            raise _fail("founding_consumed", "cap_exceeded")
        pending = [row for row in self.cases if row.is_pending]
        terminal = [row for row in self.cases if not row.is_pending]
        if len(pending) > MAX_PENDING_CASES:
            raise _fail("cases", "pending_cap_exceeded")
        if len(terminal) > MAX_TERMINAL_CASES:
            raise _fail("cases", "terminal_cap_exceeded")
        if len(self.issued_base_case_ids) > (MAX_PENDING_CASES + MAX_TERMINAL_CASES):
            raise _fail("issued_base_case_ids", "cap_exceeded")
        for name in (
            "sequence",
            "claim_sequence",
            "stance_sequence",
            "receipt_sequence",
            "case_sequence",
            "refused_claims",
            "refused_citations",
            "refused_stances",
            "refused_receipts",
            "evicted_cases",
        ):
            _require_int(name, getattr(self, name))
        if self.first_retained_tick is not None:
            _require_int("first_retained_tick", self.first_retained_tick)
        if (
            isinstance(self.last_issued_tick, bool)
            or type(self.last_issued_tick) is not int
            or self.last_issued_tick < -1
        ):
            raise _fail("last_issued_tick", "invalid_type")

        claim_ids: set[str] = set()
        for claim in self.claims:
            if type(claim) is not TheoryClaim:
                raise _fail("claims", "invalid_type")
            if claim.claim_id in claim_ids:
                raise _fail("claims", "duplicate_id")
            claim_ids.add(claim.claim_id)
        citation_ids: set[str] = set()
        for citation in self.citations:
            if type(citation) is not TheoryCitation:
                raise _fail("citations", "invalid_type")
            if citation.claim_id not in claim_ids:
                raise _fail("citations", "unknown_claim")
            if citation.citation_id in citation_ids:
                raise _fail("citations", "duplicate_id")
            citation_ids.add(citation.citation_id)
        stance_ids: set[str] = set()
        for stance in self.stances:
            if type(stance) is not TheoryStance:
                raise _fail("stances", "invalid_type")
            if stance.stance_id in stance_ids:
                raise _fail("stances", "duplicate_id")
            if stance.claim_id is not None and stance.claim_id not in claim_ids:
                raise _fail("stances", "unknown_claim")
            stance_ids.add(stance.stance_id)
        receipt_ids: set[str] = set()
        for receipt in self.receipts:
            if type(receipt) is not TheorySocialReceipt:
                raise _fail("receipts", "invalid_type")
            if receipt.claim_id not in claim_ids:
                raise _fail("receipts", "unknown_claim")
            if receipt.receipt_id in receipt_ids:
                raise _fail("receipts", "duplicate_id")
            receipt_ids.add(receipt.receipt_id)
        echo_ids: set[str] = set()
        for echo in self.echoes:
            if type(echo) is not TheorySenderEcho:
                raise _fail("echoes", "invalid_type")
            if echo.claim_id not in claim_ids:
                raise _fail("echoes", "unknown_claim")
            if echo.echo_id in echo_ids:
                raise _fail("echoes", "duplicate_id")
            echo_ids.add(echo.echo_id)
        outbound_ids: set[str] = set()
        for correlation in self.outbound:
            if type(correlation) is not TheoryOutboundCorrelation:
                raise _fail("outbound", "invalid_type")
            if correlation.claim_id not in claim_ids:
                raise _fail("outbound", "unknown_claim")
            if correlation.correlation_id in outbound_ids:
                raise _fail("outbound", "duplicate_id")
            outbound_ids.add(correlation.correlation_id)
        if len(set(self.founding_consumed)) != len(self.founding_consumed):
            raise _fail("founding_consumed", "duplicate_id")
        for digest in self.founding_consumed:
            require_stable_id("founding_consumed", digest)
        case_ids: set[str] = set()
        for case in self.cases:
            if type(case) is not TheoryForecastCase:
                raise _fail("cases", "invalid_type")
            if case.owner_id != self.owner_id:
                raise _fail("cases", "owner_mismatch")
            if case.case_id in case_ids:
                raise _fail("cases", "duplicate_id")
            for forecast in case.forecasts:
                if forecast.claim_id not in claim_ids:
                    raise _fail("cases", "unknown_claim")
            case_ids.add(case.case_id)
        if len(set(self.issued_base_case_ids)) != len(self.issued_base_case_ids):
            raise _fail("issued_base_case_ids", "duplicate_id")
        for base_case_id in self.issued_base_case_ids:
            require_stable_id("issued_base_case_ids", base_case_id)
        reason_keys: set[str] = set()
        for notice in self.coverage:
            if type(notice) is not TheoryCoverage:
                raise _fail("coverage", "invalid_type")
            if notice.reason_code in reason_keys:
                raise _fail("coverage", "duplicate_key")
            reason_keys.add(notice.reason_code)

    @property
    def pending_cases(self) -> tuple[TheoryForecastCase, ...]:
        return tuple(row for row in self.cases if row.is_pending)

    @property
    def terminal_cases(self) -> tuple[TheoryForecastCase, ...]:
        return tuple(row for row in self.cases if not row.is_pending)


def empty_competing_theory_ledger(owner_id: AgentId) -> CompetingTheoryLedger:
    """Construct an empty owner ledger. No content is copied from elsewhere."""

    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    return CompetingTheoryLedger(owner_id=owner_id)


def _bump_coverage(
    coverage: tuple[TheoryCoverage, ...], *, reason_code: str, tick: int
) -> tuple[TheoryCoverage, ...]:
    if reason_code not in _COVERAGE_REASONS:
        raise _fail("reason_code", "unknown_reason")
    for index, notice in enumerate(coverage):
        if notice.reason_code == reason_code:
            rows = list(coverage)
            rows[index] = replace(
                notice,
                first_tick=min(notice.first_tick, tick),
                last_tick=max(notice.last_tick, tick),
                count=notice.count + 1,
            )
            return tuple(rows)
    return (*coverage, TheoryCoverage(reason_code, tick, tick, 1))


def _context_equals(left: TheoryContext, right: TheoryContext) -> bool:
    return theory_context_digest(left) == theory_context_digest(right)


def theory_context_from_case(case: ForecastCase) -> TheoryContext | None:
    """Derive a transferable context from one V4-30 case, or ``None``."""

    if type(case) is not ForecastCase:
        raise _fail("case", "invalid_type")
    if case.target_kind.value == TheoryTargetKind.SEASON.value:
        target_kind = TheoryTargetKind.SEASON
    elif case.target_kind.value == TheoryTargetKind.RESOURCE_REGENERATION.value:
        target_kind = TheoryTargetKind.RESOURCE_REGENERATION
    else:
        return None
    values = {row.slot: row.value_token for row in case.conditions}
    location_id = values.get("location")
    origin_season = values.get("season")
    if location_id is None or origin_season is None:
        return None
    if target_kind is TheoryTargetKind.SEASON:
        if case.reference_resource_kind is not None:
            return None
        return TheoryContext(
            target_kind=target_kind,
            location_id=location_id,
            origin_season=origin_season,
        )
    if not case.reference_resource_kind or not case.unit_token:
        return None
    return TheoryContext(
        target_kind=target_kind,
        location_id=location_id,
        origin_season=origin_season,
        resource_kind=case.reference_resource_kind,
        unit=case.unit_token,
    )


def _claim_admission(
    ledger: CompetingTheoryLedger, incoming: TheoryClaim, *, tick: int
) -> CompetingTheoryLedger:
    existing = next(
        (row for row in ledger.claims if row.claim_id == incoming.claim_id), None
    )
    if existing is not None:
        locally_derived_tick = existing.locally_derived_tick
        if incoming.locally_derived_tick is not None and (
            locally_derived_tick is None
            or incoming.locally_derived_tick < locally_derived_tick
        ):
            locally_derived_tick = incoming.locally_derived_tick
        seed_outcome_ref = existing.seed_outcome_ref
        seed_outcome_tick = existing.seed_outcome_tick
        if incoming.seed_outcome_ref and not seed_outcome_ref:
            seed_outcome_ref = incoming.seed_outcome_ref
            seed_outcome_tick = incoming.seed_outcome_tick
        if (
            locally_derived_tick == existing.locally_derived_tick
            and seed_outcome_ref == existing.seed_outcome_ref
        ):
            return ledger
        replaced = replace(
            existing,
            locally_derived_tick=locally_derived_tick,
            seed_outcome_ref=seed_outcome_ref,
            seed_outcome_tick=seed_outcome_tick,
        )
        rows = tuple(
            replaced if row.claim_id == incoming.claim_id else row
            for row in ledger.claims
        )
        return replace(ledger, claims=rows)
    if len(ledger.claims) >= MAX_CLAIMS:
        return replace(
            ledger,
            refused_claims=ledger.refused_claims + 1,
            coverage=_bump_coverage(
                ledger.coverage, reason_code="claim_cap", tick=tick
            ),
        )
    claim = replace(incoming, sequence=ledger.claim_sequence)
    rows = tuple(sorted((*ledger.claims, claim), key=lambda row: row.registration_key))
    return replace(
        ledger,
        claims=rows,
        sequence=ledger.sequence + 1,
        claim_sequence=ledger.claim_sequence + 1,
    )


def _citation_admission(
    ledger: CompetingTheoryLedger, incoming: TheoryCitation, *, tick: int
) -> CompetingTheoryLedger:
    if incoming.claim_id not in {row.claim_id for row in ledger.claims}:
        return replace(
            ledger,
            refused_citations=ledger.refused_citations + 1,
            coverage=_bump_coverage(
                ledger.coverage, reason_code="refused_citation", tick=tick
            ),
        )
    if any(row.citation_id == incoming.citation_id for row in ledger.citations):
        return ledger
    if len(ledger.citations) >= MAX_CITATIONS:
        return replace(
            ledger,
            refused_citations=ledger.refused_citations + 1,
            coverage=_bump_coverage(
                ledger.coverage, reason_code="citation_cap", tick=tick
            ),
        )
    rows = tuple(
        sorted(
            (*ledger.citations, incoming),
            key=lambda row: (
                row.owner_tick,
                row.claim_id,
                row.polarity.value,
                row.kind.value,
                row.root_ref,
                row.provenance_ref,
            ),
        )
    )
    return replace(ledger, citations=rows, sequence=ledger.sequence + 1)


def _stance_admission(
    ledger: CompetingTheoryLedger, request: TheoryStanceRequest, *, tick: int
) -> CompetingTheoryLedger:
    claims = {row.claim_id: row for row in ledger.claims}
    if request.action is TheoryStanceAction.SUPPORT:
        claim = claims.get(request.claim_id or "")
        if claim is None or not _context_equals(claim.context, request.context):
            return replace(
                ledger,
                refused_stances=ledger.refused_stances + 1,
                coverage=_bump_coverage(
                    ledger.coverage, reason_code="stance_cap", tick=tick
                ),
            )
    if len(ledger.stances) >= MAX_STANCES:
        return replace(
            ledger,
            refused_stances=ledger.refused_stances + 1,
            coverage=_bump_coverage(
                ledger.coverage, reason_code="stance_cap", tick=tick
            ),
        )
    revision_index = sum(
        1 for row in ledger.stances if _context_equals(row.context, request.context)
    )
    claim_id = (
        request.claim_id if request.action is TheoryStanceAction.SUPPORT else None
    )
    stance = TheoryStance(
        stance_id="ths-"
        + _digest(
            ledger.owner_id.value,
            theory_context_digest(request.context),
            claim_id or "",
            request.action.value,
            str(revision_index),
        ),
        context=request.context,
        action=request.action,
        tick=tick,
        revision_index=revision_index,
        claim_id=claim_id,
    )
    rows = tuple(
        sorted(
            (*ledger.stances, stance),
            key=lambda row: (
                theory_context_digest(row.context),
                row.revision_index,
            ),
        )
    )
    return replace(
        ledger,
        stances=rows,
        sequence=ledger.sequence + 1,
        stance_sequence=ledger.stance_sequence + 1,
    )


def apply_theory_updates(
    ledger: CompetingTheoryLedger,
    *,
    tick: int,
    claims: tuple[TheoryClaim, ...] = (),
    citations: tuple[TheoryCitation, ...] = (),
    stances: tuple[TheoryStanceRequest, ...] = (),
) -> CompetingTheoryLedger:
    """Apply append-only claim, citation, and stance facts deterministically."""

    if type(ledger) is not CompetingTheoryLedger:
        raise _fail("ledger", "invalid_type")
    _require_int("tick", tick)
    claim_rows = _require_tuple("claims", claims)
    citation_rows = _require_tuple("citations", citations)
    stance_rows = _require_tuple("stances", stances)
    if len(claim_rows) > MAX_CLAIMS_PER_BUNDLE:
        raise _fail("claims", "bundle_cap")
    if len(citation_rows) > MAX_CITATIONS:
        raise _fail("citations", "bundle_cap")
    if len(stance_rows) > MAX_STANCES:
        raise _fail("stances", "bundle_cap")
    updated = ledger
    for claim in claim_rows:
        if type(claim) is not TheoryClaim:
            raise _fail("claims", "invalid_type")
        updated = _claim_admission(updated, claim, tick=tick)
    for citation in citation_rows:
        if type(citation) is not TheoryCitation:
            raise _fail("citations", "invalid_type")
        updated = _citation_admission(updated, citation, tick=tick)
    for request in stance_rows:
        if type(request) is not TheoryStanceRequest:
            raise _fail("stances", "invalid_type")
        updated = _stance_admission(updated, request, tick=tick)
    return updated


def derive_local_theory_claims(
    ledger: CompetingTheoryLedger, case: ForecastCase
) -> CompetingTheoryLedger:
    """Derive continuity and at most one recurrence claim from a scored base case."""

    if type(ledger) is not CompetingTheoryLedger:
        raise _fail("ledger", "invalid_type")
    if type(case) is not ForecastCase:
        raise _fail("case", "invalid_type")
    if case.owner_id != ledger.owner_id:
        raise _fail("case", "owner_mismatch")
    context = theory_context_from_case(case)
    tick = case.target_observation_tick
    if context is None:
        return replace(
            ledger,
            coverage=_bump_coverage(
                ledger.coverage, reason_code="unsupported_target", tick=tick
            ),
        )
    if case.observed is None:
        return ledger
    observed = case.observed.observed_class
    continuity = TheoryClaim(
        context=context,
        account=TheoryAccount.CONTINUITY,
        predicted_category=context.continuity_category,
        claim_id=theory_claim_id(
            context, TheoryAccount.CONTINUITY, context.continuity_category
        ),
        created_tick=case.issued_observation_tick,
    )
    claims = [continuity]
    citations = [
        TheoryCitation(
            claim_id=continuity.claim_id,
            owner_tick=case.issued_observation_tick,
            polarity=TheoryCitationPolarity.CONTEXT_ONLY,
            kind=TheoryCitationKind.OWN_OBSERVATION,
            root_ref=case.issued_observation_key,
            provenance_ref=case.case_id,
        )
    ]
    if observed != context.continuity_category:
        recurrence = TheoryClaim(
            context=context,
            account=TheoryAccount.RECURRENCE,
            predicted_category=observed,
            claim_id=theory_claim_id(context, TheoryAccount.RECURRENCE, observed),
            created_tick=tick,
            seed_outcome_ref=case.observed.outcome_ref,
            seed_outcome_tick=tick,
            locally_derived_tick=tick,
        )
        claims.append(recurrence)
        citations.append(
            TheoryCitation(
                claim_id=recurrence.claim_id,
                owner_tick=tick,
                polarity=TheoryCitationPolarity.SUPPORTS,
                kind=TheoryCitationKind.OWN_SCORED_CASE,
                root_ref=case.observed.outcome_ref,
                provenance_ref=case.case_id,
            )
        )
    return apply_theory_updates(
        ledger,
        tick=tick,
        claims=tuple(claims),
        citations=tuple(citations),
    )


def active_supported_claim(
    ledger: CompetingTheoryLedger, context: TheoryContext
) -> str | None:
    """Return the latest local stance claim for one context, if any."""

    if type(ledger) is not CompetingTheoryLedger:
        raise _fail("ledger", "invalid_type")
    if type(context) is not TheoryContext:
        raise _fail("context", "invalid_type")
    active: str | None = None
    for stance in ledger.stances:
        if not _context_equals(stance.context, context):
            continue
        active = stance.claim_id
    return active


def unique_citation_roots(
    citations: tuple[TheoryCitation, ...],
) -> tuple[str, ...]:
    """Count independently owned roots; inherited reports never qualify."""

    roots = {
        root
        for citation in citations
        if (root := citation.independent_root) is not None
    }
    return tuple(sorted(roots))


def competing_theory_content_count(ledger: object) -> int:
    """Count actual theory content. Empty typed headers count zero."""

    if ledger is None:
        return 0
    if type(ledger) is not CompetingTheoryLedger:
        raise _fail("ledger", "invalid_type")
    total = 0
    total += len(ledger.claims)
    total += len(ledger.citations)
    total += len(ledger.stances)
    total += len(ledger.receipts)
    total += len(ledger.cases)
    total += sum(len(row.forecasts) + len(row.outcomes) for row in ledger.cases)
    total += len(ledger.echoes)
    total += len(ledger.outbound)
    total += len(ledger.founding_consumed)
    total += len(ledger.coverage)
    total += len(ledger.issued_base_case_ids)
    for name in (
        "sequence",
        "claim_sequence",
        "stance_sequence",
        "receipt_sequence",
        "case_sequence",
        "refused_claims",
        "refused_citations",
        "refused_stances",
        "refused_receipts",
        "evicted_cases",
    ):
        total += int(getattr(ledger, name))
    if ledger.last_issued_tick >= 0:
        total += 1
    if ledger.first_retained_tick is not None:
        total += 1
    return total
