"""Owner-scoped developmental knowledge ledger and acquisition contracts.

Deepens ``generational_population`` with post-admit gradual acquisition.
Never copies peer stores, society packs, or analysis feedback into an owner.
WorldEngine remains the only objective authority; this module is subjective.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
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
    "DevelopmentalDomainId",
    "DevelopmentalDomainRate",
    "DevelopmentalKnowledgeEntry",
    "DevelopmentalKnowledgeLedger",
    "DevelopmentalSourceId",
    "DevelopmentalStageCompose",
    "empty_developmental_knowledge_ledger",
    "require_owner_developmental_knowledge",
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
