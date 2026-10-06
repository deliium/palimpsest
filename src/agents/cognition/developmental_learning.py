"""Owner-scoped developmental knowledge ledger and acquisition contracts.

Deepens ``generational_population`` with post-admit gradual acquisition.
Never copies peer stores, society packs, or analysis feedback into an owner.
WorldEngine remains the only objective authority; this module is subjective.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.models import AgentId
from world.identifiers import require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.developmental_learning"
)

DEVELOPMENTAL_LEARNING_POLICY_VERSION: Final[str] = "developmental-learning-v1"

_FORBIDDEN_DOMAIN_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "culture_pack",
        "encyclopedia",
        "society_memory",
        "inherited_language",
        "student",
        "elder_teacher",
    }
)

_FORBIDDEN_SOURCE_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "society_download",
        "parent_memory_copy",
        "global_dictionary",
        "analysis_feedback",
    }
)

_TEACHER_ALLOWED_SOURCES: Final[frozenset[str]] = frozenset(
    {"instruction", "imitation", "communication"}
)

__all__ = [
    "DEVELOPMENTAL_LEARNING_POLICY_VERSION",
    "DevelopmentalAcquisitionAudit",
    "DevelopmentalAcquisitionContext",
    "DevelopmentalAcquisitionResult",
    "DevelopmentalBudgetDecision",
    "DevelopmentalDomainId",
    "DevelopmentalDomainRate",
    "DevelopmentalKnowledgeEntry",
    "DevelopmentalKnowledgeLedger",
    "DevelopmentalSourceId",
    "DevelopmentalStageCompose",
    "apply_developmental_acquisition",
    "apply_developmental_budget_coupling",
    "compose_developmental_effective_rate",
    "empty_developmental_knowledge_ledger",
    "parse_developmental_domain_id",
    "parse_developmental_source_id",
    "require_owner_developmental_knowledge",
    "resolve_developmental_applicability",
    "resolve_developmental_rate_hints",
    "upsert_developmental_entry",
]


class DevelopmentalDomainId(StrEnum):
    """Closed owner-scoped developmental knowledge domains."""

    LOCATIONS = "locations"
    RESOURCES = "resources"
    HAZARDS = "hazards"
    SKILLS = "skills"
    SOCIAL_ACTORS = "social_actors"
    VOCABULARY = "vocabulary"
    NORMS = "norms"
    STORIES = "stories"
    PRACTICES = "practices"


class DevelopmentalSourceId(StrEnum):
    """Closed acquisition provenance sources (ledger ``source_id``)."""

    OBSERVATION = "observation"
    INSTRUCTION = "instruction"
    IMITATION = "imitation"
    COMMUNICATION = "communication"
    ARTIFACT = "artifact"
    EXPERIMENTATION = "experimentation"


class DevelopmentalStageCompose(StrEnum):
    """How domain base rates compose with lifecycle learning-rate factors."""

    MULTIPLY_LIFECYCLE_LEARNING_RATE = "multiply_lifecycle_learning_rate"
    IGNORE_LIFECYCLE = "ignore_lifecycle"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "developmental_learning_validation_failed field=%s reason_code=%s code=%s",
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


def _positive_unit(field_name: str, value: object) -> float:
    number = _finite(field_name, value)
    if number <= 0.0 or number > 1.0:
        raise _fail(field_name, "out_of_range")
    return number


def _require_tuple(field_name: str, values: object) -> tuple[object, ...]:
    if isinstance(values, (str, bytes, set, frozenset)) or not isinstance(
        values, Sequence
    ):
        raise _fail(field_name, "invalid_type")
    return tuple(values)


def _reject_forbidden_domain_alias(raw: str) -> None:
    if raw in _FORBIDDEN_DOMAIN_ALIASES:
        raise _fail("domain_id", "forbidden_domain_alias")


def _reject_forbidden_source_alias(raw: str) -> None:
    if raw in _FORBIDDEN_SOURCE_ALIASES:
        raise _fail("source_id", "forbidden_source_alias")


def parse_developmental_domain_id(value: object) -> DevelopmentalDomainId:
    """Parse a closed domain id; reject forbidden society/role aliases."""
    if type(value) is DevelopmentalDomainId:
        return value
    if not isinstance(value, str):
        raise _fail("domain_id", "unknown_domain")
    _reject_forbidden_domain_alias(value)
    try:
        return DevelopmentalDomainId(value)
    except ValueError as exc:
        raise _fail("domain_id", "unknown_domain") from exc


def parse_developmental_source_id(value: object) -> DevelopmentalSourceId:
    """Parse a closed source id; reject society-download / parent-copy aliases."""
    if type(value) is DevelopmentalSourceId:
        return value
    if not isinstance(value, str):
        raise _fail("source_id", "unknown_source")
    _reject_forbidden_source_alias(value)
    try:
        return DevelopmentalSourceId(value)
    except ValueError as exc:
        raise _fail("source_id", "unknown_source") from exc


@dataclass(frozen=True, slots=True)
class DevelopmentalDomainRate:
    """Per-domain acquisition rate knobs (runner ``domain_rates`` entry)."""

    base_rate: float
    stage_compose: DevelopmentalStageCompose = (
        DevelopmentalStageCompose.MULTIPLY_LIFECYCLE_LEARNING_RATE
    )
    min_exposures: int = 0
    confidence_floor: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "base_rate", _positive_unit("base_rate", self.base_rate)
        )
        if type(self.stage_compose) is not DevelopmentalStageCompose:
            raise _fail("stage_compose", "unknown_stage_compose")
        exposures = require_exact_nonneg_int("min_exposures", self.min_exposures)
        object.__setattr__(self, "min_exposures", exposures)
        object.__setattr__(
            self,
            "confidence_floor",
            _unit_interval("confidence_floor", self.confidence_floor),
        )


@dataclass(frozen=True, slots=True)
class DevelopmentalKnowledgeEntry:
    """One owner-scoped developmental knowledge row with acquisition provenance."""

    domain_id: DevelopmentalDomainId
    concept_key: str
    source_id: DevelopmentalSourceId
    confidence: float
    acquired_tick: int
    evidence_refs: tuple[str, ...]
    policy_version: str = DEVELOPMENTAL_LEARNING_POLICY_VERSION
    teacher_agent_id: AgentId | None = None

    def __post_init__(self) -> None:
        domain = parse_developmental_domain_id(self.domain_id)
        object.__setattr__(self, "domain_id", domain)
        source = parse_developmental_source_id(self.source_id)
        object.__setattr__(self, "source_id", source)
        concept = require_stable_id("concept_key", self.concept_key)
        object.__setattr__(self, "concept_key", concept)
        object.__setattr__(
            self, "confidence", _unit_interval("confidence", self.confidence)
        )
        tick = require_exact_nonneg_int("acquired_tick", self.acquired_tick)
        object.__setattr__(self, "acquired_tick", tick)
        if self.policy_version != DEVELOPMENTAL_LEARNING_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        refs = _require_tuple("evidence_refs", self.evidence_refs)
        checked_refs: list[str] = []
        for item in refs:
            token = require_stable_id("evidence_refs", item)
            if token not in checked_refs:
                checked_refs.append(token)
        if not checked_refs:
            raise _fail("evidence_refs", "provenance_required")
        object.__setattr__(self, "evidence_refs", tuple(checked_refs))
        teacher = self.teacher_agent_id
        if teacher is not None:
            if type(teacher) is not AgentId:
                raise _fail("teacher_agent_id", "invalid_type")
            if source.value not in _TEACHER_ALLOWED_SOURCES:
                raise _fail("teacher_agent_id", "teacher_source_forbidden")


@dataclass(frozen=True, slots=True)
class DevelopmentalKnowledgeLedger:
    """Private developmental knowledge for one owner. Content starts empty."""

    owner_id: AgentId
    entries: tuple[DevelopmentalKnowledgeEntry, ...] = ()
    policy_version: str = DEVELOPMENTAL_LEARNING_POLICY_VERSION
    max_entries_per_domain: int = 256
    # (domain_id, concept_key, exposure_count) — metadata only, no payloads.
    exposure_tallies: tuple[tuple[str, str, int], ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if self.policy_version != DEVELOPMENTAL_LEARNING_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        cap = require_exact_nonneg_int(
            "max_entries_per_domain", self.max_entries_per_domain
        )
        if cap < 1:
            raise _fail("max_entries_per_domain", "out_of_range")
        object.__setattr__(self, "max_entries_per_domain", cap)
        raw_entries = _require_tuple("entries", self.entries)
        checked: list[DevelopmentalKnowledgeEntry] = []
        seen: set[tuple[str, str]] = set()
        per_domain: dict[str, int] = {}
        for item in raw_entries:
            if type(item) is not DevelopmentalKnowledgeEntry:
                raise _fail("entries", "invalid_type")
            key = (item.domain_id.value, item.concept_key)
            if key in seen:
                raise _fail("entries", "duplicate_concept")
            seen.add(key)
            domain_key = item.domain_id.value
            per_domain[domain_key] = per_domain.get(domain_key, 0) + 1
            if per_domain[domain_key] > cap:
                raise _fail("entries", "cap_exceeded")
            checked.append(item)
        object.__setattr__(self, "entries", tuple(checked))
        raw_tallies = _require_tuple("exposure_tallies", self.exposure_tallies)
        tallies: list[tuple[str, str, int]] = []
        tally_seen: set[tuple[str, str]] = set()
        for item in raw_tallies:
            if not isinstance(item, tuple) or len(item) != 3:
                raise _fail("exposure_tallies", "invalid_type")
            domain_t = require_stable_id("exposure_tallies", item[0])
            concept_t = require_stable_id("exposure_tallies", item[1])
            count_t = require_exact_nonneg_int("exposure_tallies", item[2])
            key_t = (domain_t, concept_t)
            if key_t in tally_seen:
                raise _fail("exposure_tallies", "duplicate_concept")
            tally_seen.add(key_t)
            tallies.append((domain_t, concept_t, count_t))
        tallies.sort(key=lambda row: (row[0], row[1]))
        object.__setattr__(self, "exposure_tallies", tuple(tallies))
        _LOG.debug(
            "developmental_ledger_constructed owner_id=%s domain_count=%s "
            "entry_count=%s",
            self.owner_id.value,
            len(per_domain),
            len(checked),
        )


def empty_developmental_knowledge_ledger(
    owner_id: AgentId,
    *,
    max_entries_per_domain: int = 256,
) -> DevelopmentalKnowledgeLedger:
    """Return an empty owner ledger (modes may be on; content is empty)."""
    ledger = DevelopmentalKnowledgeLedger(
        owner_id=owner_id,
        max_entries_per_domain=max_entries_per_domain,
    )
    _LOG.debug(
        "developmental_ledger_empty owner_id=%s domain_count=%s",
        owner_id.value,
        0,
    )
    return ledger


def require_owner_developmental_knowledge(
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
    if type(ledger) is not DevelopmentalKnowledgeLedger:
        _LOG.warning("developmental_carry_rejected reason=%s", "invalid_type")
        raise TypeError(f"{field_name} must be DevelopmentalKnowledgeLedger")
    if ledger.owner_id != owner_id:
        _LOG.error(
            "developmental_validation_failed field=%s reason_code=%s",
            field_name,
            "owner_mismatch",
        )
        _LOG.warning("developmental_carry_rejected reason=%s", "owner_mismatch")
        raise ValueError(f"{field_name} owner_id mismatch")


def upsert_developmental_entry(
    ledger: DevelopmentalKnowledgeLedger,
    entry: DevelopmentalKnowledgeEntry,
) -> DevelopmentalKnowledgeLedger:
    """Append or replace one entry; reject provenance-less writes fail-closed.

    Deterministic eviction drops the oldest entry in the same domain when the
    per-domain cap would be exceeded.
    """
    if type(ledger) is not DevelopmentalKnowledgeLedger:
        raise _fail("ledger", "invalid_type")
    if type(entry) is not DevelopmentalKnowledgeEntry:
        raise _fail("entry", "invalid_type")
    # Re-validate provenance gate explicitly for call sites that bypass
    # DevelopmentalKnowledgeEntry construction (e.g. mocks).
    if not entry.evidence_refs:
        _LOG.error(
            "developmental_write_rejected owner_id=%s reason_code=%s code=%s",
            ledger.owner_id.value,
            "provenance_required",
            "provenance_required",
        )
        raise ValueError("evidence_refs: provenance_required")

    kept: list[DevelopmentalKnowledgeEntry] = []
    replaced = False
    for existing in ledger.entries:
        if (
            existing.domain_id == entry.domain_id
            and existing.concept_key == entry.concept_key
        ):
            kept.append(entry)
            replaced = True
        else:
            kept.append(existing)
    if not replaced:
        kept.append(entry)

    domain = entry.domain_id
    domain_rows = [row for row in kept if row.domain_id == domain]
    if len(domain_rows) > ledger.max_entries_per_domain:
        # Evict oldest by acquired_tick then concept_key for stability.
        domain_rows_sorted = sorted(
            domain_rows,
            key=lambda row: (row.acquired_tick, row.concept_key),
        )
        drop = domain_rows_sorted[0]
        kept = [row for row in kept if row is not drop]
        _LOG.warning(
            "developmental_eviction owner_id=%s domain=%s concept_key=%s",
            ledger.owner_id.value,
            domain.value,
            drop.concept_key,
        )

    result = DevelopmentalKnowledgeLedger(
        owner_id=ledger.owner_id,
        entries=tuple(kept),
        policy_version=ledger.policy_version,
        max_entries_per_domain=ledger.max_entries_per_domain,
        exposure_tallies=ledger.exposure_tallies,
    )
    _LOG.debug(
        "developmental_write owner_id=%s domain=%s source=%s teacher_present=%s "
        "confidence=%s",
        ledger.owner_id.value,
        entry.domain_id.value,
        entry.source_id.value,
        entry.teacher_agent_id is not None,
        entry.confidence,
    )
    return result


def compose_developmental_effective_rate(
    *,
    owner_id: AgentId,
    domain: DevelopmentalDomainId | str,
    base_rate: float,
    source_weight: float,
    stage_compose: DevelopmentalStageCompose | str,
    lifecycle_factor: float = 1.0,
    learning_rate_zero: bool = False,
    exposure_count: int = 0,
    min_exposures: int = 0,
) -> float:
    """Compose effective acquisition rate (locked order).

    1. dependency ``learning_rate_zero`` → 0
    2. ``stage_compose`` multiply by lifecycle factor (or ignore)
    3. ``base_rate`` x source weight
    """
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    domain_id = parse_developmental_domain_id(domain)
    base = _positive_unit("base_rate", base_rate)
    weight = _positive_unit("source_weight", source_weight)
    if type(stage_compose) is not DevelopmentalStageCompose:
        try:
            compose = DevelopmentalStageCompose(str(stage_compose))
        except ValueError as exc:
            raise _fail("stage_compose", "unknown_stage_compose") from exc
    else:
        compose = stage_compose
    exposures = require_exact_nonneg_int("exposure_count", exposure_count)
    min_exp = require_exact_nonneg_int("min_exposures", min_exposures)
    if type(learning_rate_zero) is not bool:
        raise _fail("learning_rate_zero", "invalid_type")
    factor = _finite("lifecycle_factor", lifecycle_factor)
    if factor < 0.0:
        raise _fail("lifecycle_factor", "out_of_range")

    if learning_rate_zero:
        effective = 0.0
    elif exposures < min_exp:
        effective = 0.0
    else:
        lifecycle = (
            factor
            if compose is DevelopmentalStageCompose.MULTIPLY_LIFECYCLE_LEARNING_RATE
            else 1.0
        )
        effective = base * weight * lifecycle
        if effective < 0.0:
            effective = 0.0
        if effective > 1.0:
            effective = 1.0
    _LOG.debug(
        "developmental_rate_compose owner_id=%s domain=%s base_rate=%s "
        "lifecycle_factor=%s source_weight=%s learning_rate_zero=%s "
        "effective_rate=%s",
        owner_id.value,
        domain_id.value,
        base,
        factor,
        weight,
        learning_rate_zero,
        effective,
    )
    return effective


@dataclass(frozen=True, slots=True)
class DevelopmentalBudgetDecision:
    """Outcome of cognitive-budget coupling for one acquisition attempt."""

    proceed: bool
    effective_rate: float
    reason_code: str
    remaining: int
    cost: int
    policy: str


def apply_developmental_budget_coupling(
    *,
    owner_id: AgentId,
    effective_rate: float,
    coupling_mode: str,
    degrade_policy: str,
    acquisition_cost_units: int,
    budget_enforced: bool,
    budget_ledger: object | None = None,
) -> DevelopmentalBudgetDecision:
    """Apply cognitive-budget coupling without skipping the closed command.

    ``ignore`` leaves rate untouched. ``respect_enforced`` charges the ledger
    when ``CognitiveBudgetMode.ENFORCED`` and applies ``skip_acquisition`` or
    ``reduce_rate``.
    """
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    rate = _unit_interval("effective_rate", effective_rate)
    mode = require_stable_id("coupling_mode", coupling_mode)
    policy = require_stable_id("degrade_policy", degrade_policy)
    cost = require_exact_nonneg_int("acquisition_cost_units", acquisition_cost_units)
    if type(budget_enforced) is not bool:
        raise _fail("budget_enforced", "invalid_type")
    if mode not in {"ignore", "respect_enforced"}:
        raise _fail("coupling_mode", "unknown_mode")
    if policy not in {"skip_acquisition", "reduce_rate"}:
        raise _fail("degrade_policy", "unknown_policy")

    remaining = -1
    if mode == "ignore" or not budget_enforced or cost == 0:
        decision = DevelopmentalBudgetDecision(
            proceed=True,
            effective_rate=rate,
            reason_code="budget_passthrough",
            remaining=remaining,
            cost=cost,
            policy=policy,
        )
        _LOG.debug(
            "developmental_budget owner_id=%s remaining=%s cost=%s policy=%s "
            "acquired=%s",
            owner_id.value,
            remaining,
            cost,
            policy,
            True,
        )
        return decision

    from agents.cognition.budget import BudgetDimension, TickBudgetLedger

    if budget_ledger is None or type(budget_ledger) is not TickBudgetLedger:
        decision = DevelopmentalBudgetDecision(
            proceed=False,
            effective_rate=0.0,
            reason_code="budget_ledger_missing",
            remaining=0,
            cost=cost,
            policy=policy,
        )
        _LOG.debug(
            "developmental_budget owner_id=%s remaining=%s cost=%s policy=%s "
            "acquired=%s",
            owner_id.value,
            0,
            cost,
            policy,
            False,
        )
        return decision

    remaining = int(budget_ledger.remaining(BudgetDimension.MEMORIES))
    charged = budget_ledger.try_consume(BudgetDimension.MEMORIES, cost)
    if charged:
        decision = DevelopmentalBudgetDecision(
            proceed=True,
            effective_rate=rate,
            reason_code="budget_charged",
            remaining=int(budget_ledger.remaining(BudgetDimension.MEMORIES)),
            cost=cost,
            policy=policy,
        )
        _LOG.debug(
            "developmental_budget owner_id=%s remaining=%s cost=%s policy=%s "
            "acquired=%s",
            owner_id.value,
            decision.remaining,
            cost,
            policy,
            True,
        )
        return decision

    if policy == "skip_acquisition":
        decision = DevelopmentalBudgetDecision(
            proceed=False,
            effective_rate=0.0,
            reason_code="budget_skip_acquisition",
            remaining=remaining,
            cost=cost,
            policy=policy,
        )
    else:
        reduced = rate * 0.5
        decision = DevelopmentalBudgetDecision(
            proceed=True,
            effective_rate=reduced,
            reason_code="budget_reduce_rate",
            remaining=remaining,
            cost=cost,
            policy=policy,
        )
    _LOG.debug(
        "developmental_budget owner_id=%s remaining=%s cost=%s policy=%s "
        "acquired=%s",
        owner_id.value,
        decision.remaining,
        cost,
        policy,
        decision.proceed,
    )
    return decision


def _confidence_band(confidence: float) -> str:
    if confidence <= 0.0:
        return "none"
    if confidence < 0.34:
        return "low"
    if confidence < 0.67:
        return "mid"
    return "high"


@dataclass(frozen=True, slots=True)
class DevelopmentalAcquisitionAudit:
    """Metadata-only acquisition attempt record (no concept payloads)."""

    owner_id: AgentId
    domain_id: DevelopmentalDomainId
    source_id: DevelopmentalSourceId
    tick: int
    acquired: bool
    confidence_band: str
    reason_code: str
    teacher_present: bool
    teacher_agent_id: AgentId | None = None
    exposures_to_acquisition: int | None = None

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        object.__setattr__(
            self, "domain_id", parse_developmental_domain_id(self.domain_id)
        )
        object.__setattr__(
            self, "source_id", parse_developmental_source_id(self.source_id)
        )
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))
        if type(self.acquired) is not bool:
            raise _fail("acquired", "invalid_type")
        band = require_stable_id("confidence_band", self.confidence_band)
        if band not in {"none", "low", "mid", "high"}:
            raise _fail("confidence_band", "unknown_band")
        object.__setattr__(self, "confidence_band", band)
        object.__setattr__(
            self, "reason_code", require_stable_id("reason_code", self.reason_code)
        )
        if type(self.teacher_present) is not bool:
            raise _fail("teacher_present", "invalid_type")
        teacher = self.teacher_agent_id
        if teacher is not None and type(teacher) is not AgentId:
            raise _fail("teacher_agent_id", "invalid_type")
        if teacher is not None and not self.teacher_present:
            raise _fail("teacher_present", "teacher_mismatch")
        exposures = self.exposures_to_acquisition
        if exposures is not None:
            object.__setattr__(
                self,
                "exposures_to_acquisition",
                require_exact_nonneg_int("exposures_to_acquisition", exposures),
            )


@dataclass(frozen=True, slots=True)
class DevelopmentalAcquisitionContext:
    """Per-tick knobs for acquisition (modes, rates, budgets). Duck-typed inputs."""

    lifecycle_factor: float = 1.0
    learning_rate_zero: bool = False
    budget_enforced: bool = False
    budget_ledger: object | None = None
    predictive_world_model: bool = False
    skill_learning_on: bool = False
    teaching_on: bool = False
    semantic_naming_on: bool = False
    social_norm_on: bool = False
    social_convention_on: bool = False
    cultural_narrative_on: bool = False
    artifact_interpretation_on: bool = False
    advice_delta: tuple[object, ...] = ()
    applicable: bool = True


def resolve_developmental_rate_hints(
    observation: object,
    *,
    stage_learning_rates: Mapping[str, float] | None = None,
    entity_learning_rate: float | None = None,
) -> tuple[float, bool]:
    """Derive lifecycle factor and learning_rate_zero from Observation + rates.

    ``learning_rate_zero`` follows a critical ``learning`` dependency need on
    ``self_body`` (same signal as objective dependency-care consequence).

    ``lifecycle_factor`` prefers objective ``entity_learning_rate`` (engine
    continuous / ``learning_rate_by_entity``) when present — that already embeds
    stage + gradual-aging. Otherwise falls back to the stage→rate table from
    ``population_lifecycle.stage_capability_effects``.
    """
    learning_rate_zero = False
    stage: str | None = None
    body = getattr(observation, "self_body", None)
    if body is not None:
        lifecycle = getattr(body, "lifecycle", None)
        if lifecycle is not None:
            raw_stage = getattr(lifecycle, "stage", None)
            if isinstance(raw_stage, str):
                stage = raw_stage
        needs = getattr(body, "dependency_needs", None)
        rows = getattr(needs, "needs", ()) if needs is not None else ()
        for row in rows:
            if (
                getattr(row, "need_id", None) == "learning"
                and bool(getattr(row, "critical", False))
            ):
                learning_rate_zero = True
                break
    if entity_learning_rate is not None:
        factor = _finite("entity_learning_rate", float(entity_learning_rate))
        if factor < 0.0:
            raise _fail("entity_learning_rate", "out_of_range")
        return factor, learning_rate_zero
    factor = 1.0
    if stage is not None and stage_learning_rates:
        raw = stage_learning_rates.get(stage)
        if raw is not None:
            factor = _finite("lifecycle_factor", float(raw))
            if factor < 0.0:
                raise _fail("lifecycle_factor", "out_of_range")
    return factor, learning_rate_zero


def resolve_developmental_applicability(
    *,
    applicability: str,
    observation: object,
    mid_run_admit: bool,
) -> bool:
    """Return whether this owner should run developmental acquisition this tick."""
    mode = require_stable_id("applicability", applicability)
    if mode == "all_live_agents":
        return True
    if mode == "mid_run_new_agents":
        return bool(mid_run_admit)
    if mode == "lifecycle_learning_stage":
        body = getattr(observation, "self_body", None)
        lifecycle = getattr(body, "lifecycle", None) if body is not None else None
        stage = getattr(lifecycle, "stage", None) if lifecycle is not None else None
        return stage == "learning"
    raise _fail("applicability", "unknown_applicability")


@dataclass(frozen=True, slots=True)
class DevelopmentalAcquisitionResult:
    """Updated ledger plus metadata audits from one acquisition pass."""

    ledger: DevelopmentalKnowledgeLedger
    audits: tuple[DevelopmentalAcquisitionAudit, ...]
    world_model_uplift: bool


@dataclass(frozen=True, slots=True)
class _AcquisitionCandidate:
    domain: DevelopmentalDomainId
    source: DevelopmentalSourceId
    concept_key: str
    evidence_ref: str
    teacher_agent_id: AgentId | None = None


_DOMAIN_MODE_GATES: Final[Mapping[str, str]] = {
    DevelopmentalDomainId.SKILLS.value: "skill_learning_on",
    DevelopmentalDomainId.VOCABULARY.value: "semantic_naming_on",
    DevelopmentalDomainId.NORMS.value: "social_norm_on",
    DevelopmentalDomainId.STORIES.value: "cultural_narrative_on",
    DevelopmentalDomainId.PRACTICES.value: "social_convention_on",
}


def _mode_allows(
    domain: DevelopmentalDomainId, context: DevelopmentalAcquisitionContext
) -> bool:
    gate = _DOMAIN_MODE_GATES.get(domain.value)
    if gate is None:
        return True
    return bool(getattr(context, gate, False))


def _collect_observation_candidates(
    observation: object,
    *,
    enabled_domains: frozenset[str],
    enabled_sources: frozenset[str],
) -> list[_AcquisitionCandidate]:
    from world.observations import Observation

    if type(observation) is not Observation:
        return []
    tick = observation.tick
    out: list[_AcquisitionCandidate] = []
    if DevelopmentalSourceId.OBSERVATION.value in enabled_sources:
        if DevelopmentalDomainId.LOCATIONS.value in enabled_domains:
            for loc in observation.locations:
                out.append(
                    _AcquisitionCandidate(
                        domain=DevelopmentalDomainId.LOCATIONS,
                        source=DevelopmentalSourceId.OBSERVATION,
                        concept_key=f"loc:{loc.entity_id.value}",
                        evidence_ref=f"obs:{tick}:loc:{loc.entity_id.value}",
                    )
                )
            self_body = observation.self_body
            if self_body is not None:
                out.append(
                    _AcquisitionCandidate(
                        domain=DevelopmentalDomainId.LOCATIONS,
                        source=DevelopmentalSourceId.OBSERVATION,
                        concept_key=f"loc:{self_body.location_id.value}",
                        evidence_ref=f"obs:{tick}:self_loc:{self_body.location_id.value}",
                    )
                )
        if DevelopmentalDomainId.RESOURCES.value in enabled_domains:
            for resource in observation.resources:
                out.append(
                    _AcquisitionCandidate(
                        domain=DevelopmentalDomainId.RESOURCES,
                        source=DevelopmentalSourceId.OBSERVATION,
                        concept_key=f"res:{resource.entity_id.value}",
                        evidence_ref=f"obs:{tick}:res:{resource.entity_id.value}",
                    )
                )
        if DevelopmentalDomainId.HAZARDS.value in enabled_domains:
            hazards = observation.hazard_kinds or ()
            for hazard in hazards:
                kind = getattr(hazard, "value", str(hazard))
                out.append(
                    _AcquisitionCandidate(
                        domain=DevelopmentalDomainId.HAZARDS,
                        source=DevelopmentalSourceId.OBSERVATION,
                        concept_key=f"haz:{kind}",
                        evidence_ref=f"obs:{tick}:haz:{kind}",
                    )
                )
        if DevelopmentalDomainId.SOCIAL_ACTORS.value in enabled_domains:
            for body in observation.visible_bodies:
                out.append(
                    _AcquisitionCandidate(
                        domain=DevelopmentalDomainId.SOCIAL_ACTORS,
                        source=DevelopmentalSourceId.OBSERVATION,
                        concept_key=f"actor:{body.entity_id.value}",
                        evidence_ref=f"obs:{tick}:actor:{body.entity_id.value}",
                    )
                )
    if DevelopmentalSourceId.EXPERIMENTATION.value in enabled_sources:
        for occurrence in observation.occurrences:
            kind = str(getattr(occurrence, "kind", "")).lower()
            if "fail" not in kind and "success" not in kind and "trial" not in kind:
                continue
            event_id = getattr(occurrence.provenance, "event_id", None)
            evidence = (
                f"evt:{event_id.value}"
                if event_id is not None and hasattr(event_id, "value")
                else f"occ:{tick}:{kind}"
            )
            if DevelopmentalDomainId.SKILLS.value in enabled_domains:
                out.append(
                    _AcquisitionCandidate(
                        domain=DevelopmentalDomainId.SKILLS,
                        source=DevelopmentalSourceId.EXPERIMENTATION,
                        concept_key=f"skill:trial:{kind}",
                        evidence_ref=evidence,
                    )
                )
            if DevelopmentalDomainId.PRACTICES.value in enabled_domains:
                out.append(
                    _AcquisitionCandidate(
                        domain=DevelopmentalDomainId.PRACTICES,
                        source=DevelopmentalSourceId.EXPERIMENTATION,
                        concept_key=f"practice:trial:{kind}",
                        evidence_ref=evidence,
                    )
                )
    if DevelopmentalSourceId.COMMUNICATION.value in enabled_sources:
        for comm in observation.communications:
            speaker = getattr(comm, "speaker_id", None) or getattr(
                comm, "source_id", None
            )
            teacher = None
            if speaker is not None:
                token = getattr(speaker, "value", str(speaker))
                teacher = AgentId(token) if token else None
            action = getattr(comm, "action_kind", "talk")
            domains_for_comm = (
                DevelopmentalDomainId.VOCABULARY,
                DevelopmentalDomainId.SOCIAL_ACTORS,
                DevelopmentalDomainId.STORIES,
            )
            for domain in domains_for_comm:
                if domain.value not in enabled_domains:
                    continue
                out.append(
                    _AcquisitionCandidate(
                        domain=domain,
                        source=DevelopmentalSourceId.COMMUNICATION,
                        concept_key=f"comm:{action}:{tick}",
                        evidence_ref=f"comm:{tick}:{action}",
                        teacher_agent_id=teacher,
                    )
                )
    if DevelopmentalSourceId.IMITATION.value in enabled_sources:
        for occurrence in observation.occurrences:
            other = getattr(occurrence, "other_entity_id", None)
            if other is None:
                continue
            kind = str(getattr(occurrence, "kind", "act")).lower()
            if "success" not in kind and "complete" not in kind:
                continue
            other_token = other.value if hasattr(other, "value") else str(other)
            teacher = AgentId(other_token)
            if DevelopmentalDomainId.PRACTICES.value in enabled_domains:
                out.append(
                    _AcquisitionCandidate(
                        domain=DevelopmentalDomainId.PRACTICES,
                        source=DevelopmentalSourceId.IMITATION,
                        concept_key=f"practice:imit:{kind}",
                        evidence_ref=f"imit:{tick}:{other_token}",
                        teacher_agent_id=teacher,
                    )
                )
            if DevelopmentalDomainId.SKILLS.value in enabled_domains:
                out.append(
                    _AcquisitionCandidate(
                        domain=DevelopmentalDomainId.SKILLS,
                        source=DevelopmentalSourceId.IMITATION,
                        concept_key=f"skill:imit:{kind}",
                        evidence_ref=f"imit:{tick}:skill:{kind}",
                        teacher_agent_id=teacher,
                    )
                )
    if DevelopmentalSourceId.ARTIFACT.value in enabled_sources:
        for artifact in observation.artifacts:
            aid = artifact.entity_id.value
            if DevelopmentalDomainId.VOCABULARY.value in enabled_domains:
                out.append(
                    _AcquisitionCandidate(
                        domain=DevelopmentalDomainId.VOCABULARY,
                        source=DevelopmentalSourceId.ARTIFACT,
                        concept_key=f"vocab:art:{aid}",
                        evidence_ref=f"art:{aid}",
                    )
                )
            if DevelopmentalDomainId.PRACTICES.value in enabled_domains:
                out.append(
                    _AcquisitionCandidate(
                        domain=DevelopmentalDomainId.PRACTICES,
                        source=DevelopmentalSourceId.ARTIFACT,
                        concept_key=f"practice:art:{aid}",
                        evidence_ref=f"art:{aid}",
                    )
                )
            if DevelopmentalDomainId.LOCATIONS.value in enabled_domains:
                out.append(
                    _AcquisitionCandidate(
                        domain=DevelopmentalDomainId.LOCATIONS,
                        source=DevelopmentalSourceId.ARTIFACT,
                        concept_key=f"loc:art:{aid}",
                        evidence_ref=f"art:{aid}",
                    )
                )
    return out


def _collect_instruction_candidates(
    advice_delta: Sequence[object],
    *,
    enabled_domains: frozenset[str],
    enabled_sources: frozenset[str],
) -> list[_AcquisitionCandidate]:
    if DevelopmentalSourceId.INSTRUCTION.value not in enabled_sources:
        return []
    out: list[_AcquisitionCandidate] = []
    for row in advice_delta:
        teacher = getattr(row, "source_agent_id", None)
        if type(teacher) is not AgentId:
            teacher = None
        domain_token = getattr(getattr(row, "domain", None), "value", None) or str(
            getattr(row, "domain", "skill")
        )
        occurrence = getattr(row, "occurrence_id", "teach")
        mapped = DevelopmentalDomainId.SKILLS
        if "norm" in domain_token.lower():
            mapped = DevelopmentalDomainId.NORMS
        elif "practice" in domain_token.lower() or "convention" in domain_token.lower():
            mapped = DevelopmentalDomainId.PRACTICES
        elif "vocab" in domain_token.lower() or "name" in domain_token.lower():
            mapped = DevelopmentalDomainId.VOCABULARY
        elif "stor" in domain_token.lower() or "narrative" in domain_token.lower():
            mapped = DevelopmentalDomainId.STORIES
        if mapped.value not in enabled_domains:
            continue
        out.append(
            _AcquisitionCandidate(
                domain=mapped,
                source=DevelopmentalSourceId.INSTRUCTION,
                concept_key=f"instr:{domain_token}:{occurrence}",
                evidence_ref=f"teach:{occurrence}",
                teacher_agent_id=teacher,
            )
        )
    return out


def _bump_exposure_tally(
    ledger: DevelopmentalKnowledgeLedger,
    *,
    domain: DevelopmentalDomainId,
    concept_key: str,
) -> tuple[DevelopmentalKnowledgeLedger, int]:
    """Increment owner/domain/concept exposure count; return (ledger, count)."""
    tallies: dict[tuple[str, str], int] = {
        (domain_id, concept): count
        for domain_id, concept, count in ledger.exposure_tallies
    }
    key = (domain.value, concept_key)
    count = tallies.get(key, 0) + 1
    tallies[key] = count
    updated = DevelopmentalKnowledgeLedger(
        owner_id=ledger.owner_id,
        entries=ledger.entries,
        policy_version=ledger.policy_version,
        max_entries_per_domain=ledger.max_entries_per_domain,
        exposure_tallies=tuple(
            (domain_id, concept, n)
            for (domain_id, concept), n in sorted(tallies.items())
        ),
    )
    return updated, count


def apply_developmental_acquisition(
    ledger: DevelopmentalKnowledgeLedger,
    *,
    spec: object,
    observation: object,
    context: DevelopmentalAcquisitionContext | None = None,
) -> DevelopmentalAcquisitionResult:
    """Apply enabled domain/source adapters; never copy peer subjective stores.

    CausalWorldModel uplift is reported as eligible only when
    ``context.predictive_world_model`` is true; this function does not mutate
    world-model state (existing loop path owns that).
    """
    if type(ledger) is not DevelopmentalKnowledgeLedger:
        raise _fail("ledger", "invalid_type")
    ctx = context if context is not None else DevelopmentalAcquisitionContext()
    mode = getattr(spec, "developmental_learning_mode", None)
    if mode != "deterministic":
        _LOG.debug(
            "developmental_acquisition_skip owner_id=%s reason_code=%s",
            ledger.owner_id.value,
            "channel_mode_off",
        )
        return DevelopmentalAcquisitionResult(
            ledger=ledger, audits=(), world_model_uplift=False
        )
    if not ctx.applicable:
        _LOG.debug(
            "developmental_acquisition_skip owner_id=%s reason_code=%s",
            ledger.owner_id.value,
            "applicability_filtered",
        )
        return DevelopmentalAcquisitionResult(
            ledger=ledger, audits=(), world_model_uplift=False
        )

    enabled_domains = frozenset(str(d) for d in getattr(spec, "enabled_domains", ()))
    enabled_sources = frozenset(str(s) for s in getattr(spec, "enabled_sources", ()))
    domain_rates = getattr(spec, "domain_rates", {})
    source_weights = getattr(spec, "source_weights", {})
    coupling = getattr(spec, "cognitive_budget_coupling", None)
    coupling_mode = getattr(coupling, "mode", "ignore") if coupling else "ignore"
    degrade_policy = (
        getattr(coupling, "degrade_policy", "skip_acquisition")
        if coupling
        else "skip_acquisition"
    )
    acquisition_cost = (
        int(getattr(coupling, "acquisition_cost_units", 0)) if coupling else 0
    )

    candidates = _collect_observation_candidates(
        observation,
        enabled_domains=enabled_domains,
        enabled_sources=enabled_sources,
    )
    candidates.extend(
        _collect_instruction_candidates(
            ctx.advice_delta,
            enabled_domains=enabled_domains,
            enabled_sources=enabled_sources,
        )
    )

    # Deterministic order: domain, source, concept_key.
    candidates.sort(
        key=lambda c: (c.domain.value, c.source.value, c.concept_key, c.evidence_ref)
    )

    tick = int(getattr(observation, "tick", 0))
    audits: list[DevelopmentalAcquisitionAudit] = []
    current = ledger
    world_model_uplift = False
    spatial_domains = {
        DevelopmentalDomainId.LOCATIONS,
        DevelopmentalDomainId.RESOURCES,
        DevelopmentalDomainId.HAZARDS,
    }

    for candidate in candidates:
        if candidate.domain.value not in enabled_domains:
            continue
        if candidate.source.value not in enabled_sources:
            continue
        current, exposure_count = _bump_exposure_tally(
            current,
            domain=candidate.domain,
            concept_key=candidate.concept_key,
        )
        if not _mode_allows(candidate.domain, ctx):
            if (
                candidate.source is DevelopmentalSourceId.ARTIFACT
                and not ctx.artifact_interpretation_on
            ):
                reason = "artifact_mode_off"
            else:
                reason = "required_mode_off"
            _LOG.debug(
                "developmental_acquisition_skip owner_id=%s domain=%s source=%s "
                "reason_code=%s",
                ledger.owner_id.value,
                candidate.domain.value,
                candidate.source.value,
                reason,
            )
            audits.append(
                DevelopmentalAcquisitionAudit(
                    owner_id=ledger.owner_id,
                    domain_id=candidate.domain,
                    source_id=candidate.source,
                    tick=tick,
                    acquired=False,
                    confidence_band="none",
                    reason_code=reason,
                    teacher_present=candidate.teacher_agent_id is not None,
                    teacher_agent_id=candidate.teacher_agent_id,
                )
            )
            continue
        if (
            candidate.source is DevelopmentalSourceId.ARTIFACT
            and not ctx.artifact_interpretation_on
        ):
            _LOG.debug(
                "developmental_acquisition_skip owner_id=%s domain=%s source=%s "
                "reason_code=%s",
                ledger.owner_id.value,
                candidate.domain.value,
                candidate.source.value,
                "artifact_mode_off",
            )
            audits.append(
                DevelopmentalAcquisitionAudit(
                    owner_id=ledger.owner_id,
                    domain_id=candidate.domain,
                    source_id=candidate.source,
                    tick=tick,
                    acquired=False,
                    confidence_band="none",
                    reason_code="artifact_mode_off",
                    teacher_present=False,
                )
            )
            continue

        rate_obj = domain_rates.get(candidate.domain.value)
        if rate_obj is None:
            continue
        base_rate = float(getattr(rate_obj, "base_rate", 0.0))
        stage_compose = getattr(
            rate_obj,
            "stage_compose",
            DevelopmentalStageCompose.MULTIPLY_LIFECYCLE_LEARNING_RATE,
        )
        min_exposures = int(getattr(rate_obj, "min_exposures", 0))
        confidence_floor = float(getattr(rate_obj, "confidence_floor", 0.0))
        source_weight = float(source_weights.get(candidate.source.value, 0.0))
        if source_weight <= 0.0:
            continue

        already = any(
            row.domain_id is candidate.domain
            and row.concept_key == candidate.concept_key
            for row in current.entries
        )
        effective = compose_developmental_effective_rate(
            owner_id=ledger.owner_id,
            domain=candidate.domain,
            base_rate=base_rate,
            source_weight=source_weight,
            stage_compose=stage_compose,
            lifecycle_factor=ctx.lifecycle_factor,
            learning_rate_zero=ctx.learning_rate_zero,
            exposure_count=exposure_count,
            min_exposures=min_exposures,
        )
        if effective <= 0.0:
            audits.append(
                DevelopmentalAcquisitionAudit(
                    owner_id=ledger.owner_id,
                    domain_id=candidate.domain,
                    source_id=candidate.source,
                    tick=tick,
                    acquired=False,
                    confidence_band="none",
                    reason_code="rate_zero",
                    teacher_present=candidate.teacher_agent_id is not None,
                    teacher_agent_id=candidate.teacher_agent_id,
                )
            )
            continue

        budget = apply_developmental_budget_coupling(
            owner_id=ledger.owner_id,
            effective_rate=effective,
            coupling_mode=str(coupling_mode),
            degrade_policy=str(degrade_policy),
            acquisition_cost_units=acquisition_cost,
            budget_enforced=ctx.budget_enforced,
            budget_ledger=ctx.budget_ledger,
        )
        if not budget.proceed:
            audits.append(
                DevelopmentalAcquisitionAudit(
                    owner_id=ledger.owner_id,
                    domain_id=candidate.domain,
                    source_id=candidate.source,
                    tick=tick,
                    acquired=False,
                    confidence_band="none",
                    reason_code=budget.reason_code,
                    teacher_present=candidate.teacher_agent_id is not None,
                    teacher_agent_id=candidate.teacher_agent_id,
                )
            )
            continue

        confidence = max(confidence_floor, budget.effective_rate)
        if confidence <= 0.0:
            audits.append(
                DevelopmentalAcquisitionAudit(
                    owner_id=ledger.owner_id,
                    domain_id=candidate.domain,
                    source_id=candidate.source,
                    tick=tick,
                    acquired=False,
                    confidence_band="none",
                    reason_code="confidence_floor_blocked",
                    teacher_present=candidate.teacher_agent_id is not None,
                    teacher_agent_id=candidate.teacher_agent_id,
                )
            )
            continue

        entry = DevelopmentalKnowledgeEntry(
            domain_id=candidate.domain,
            concept_key=candidate.concept_key,
            source_id=candidate.source,
            confidence=confidence,
            acquired_tick=tick,
            evidence_refs=(candidate.evidence_ref,),
            teacher_agent_id=candidate.teacher_agent_id,
        )
        current = upsert_developmental_entry(current, entry)
        uplift = (
            candidate.domain in spatial_domains
            and candidate.source
            in {
                DevelopmentalSourceId.OBSERVATION,
                DevelopmentalSourceId.EXPERIMENTATION,
            }
            and ctx.predictive_world_model
        )
        if candidate.domain in spatial_domains and not ctx.predictive_world_model:
            _LOG.debug(
                "developmental_acquisition owner_id=%s domain=%s source=%s "
                "ledger_touch=%s world_model_uplift=%s",
                ledger.owner_id.value,
                candidate.domain.value,
                candidate.source.value,
                True,
                False,
            )
        else:
            _LOG.debug(
                "developmental_acquisition owner_id=%s domain=%s source=%s "
                "ledger_touch=%s world_model_uplift=%s",
                ledger.owner_id.value,
                candidate.domain.value,
                candidate.source.value,
                True,
                uplift,
            )
        if uplift:
            world_model_uplift = True
        if candidate.source is DevelopmentalSourceId.INSTRUCTION:
            _LOG.info(
                "developmental_instruction_acquired owner_id=%s domain=%s "
                "teacher_id=%s source=%s",
                ledger.owner_id.value,
                candidate.domain.value,
                None
                if candidate.teacher_agent_id is None
                else candidate.teacher_agent_id.value,
                candidate.source.value,
            )
        audits.append(
            DevelopmentalAcquisitionAudit(
                owner_id=ledger.owner_id,
                domain_id=candidate.domain,
                source_id=candidate.source,
                tick=tick,
                acquired=True,
                confidence_band=_confidence_band(confidence),
                reason_code="acquired",
                teacher_present=candidate.teacher_agent_id is not None,
                teacher_agent_id=candidate.teacher_agent_id,
                exposures_to_acquisition=None if already else exposure_count,
            )
        )

    return DevelopmentalAcquisitionResult(
        ledger=current,
        audits=tuple(audits),
        world_model_uplift=world_model_uplift,
    )
