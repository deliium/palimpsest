"""Owner-scoped practical-knowledge ledger and genealogy contracts.

Deepens ``cultural_historical_memory`` with transferable technique lineages
(owner-local multi-parent DAGs). Objective skill levels stay in WorldEngine;
research genealogy queries stay in ``analysis``. Never copies peer ledgers,
society technique packs, or analysis DAGs into live cognition.
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

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.practical_knowledge")

PRACTICAL_KNOWLEDGE_POLICY_VERSION: Final[str] = "practical-knowledge-v1"
PRACTICAL_KNOWLEDGE_FIRST_HOP_INDEX: Final[int] = 0
PRACTICAL_KNOWLEDGE_MAX_HOP_DEPTH_CEILING: Final[int] = 32
_DISTANCE_QUANTUM: Final[float] = 1e-6
_CONTENT_KEY_PREFIX: Final[str] = "tech:"

_FORBIDDEN_KIND_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "global_technique_registry",
        "society_encyclopedia",
        "true_method_catalog",
        "knowledge_pack",
        "parent_technique_copy",
        "technique_pack",
        "GlobalTechniqueRegistry",
        "GlobalKnowledge",
        "TechniqueRegistry",
    }
)

__all__ = [
    "PRACTICAL_KNOWLEDGE_FIRST_HOP_INDEX",
    "PRACTICAL_KNOWLEDGE_MAX_HOP_DEPTH_CEILING",
    "PRACTICAL_KNOWLEDGE_POLICY_VERSION",
    "KnowledgeTransmissionOrigin",
    "PracticalKnowledgeAudit",
    "PracticalKnowledgeKind",
    "PracticalKnowledgeLedger",
    "SubjectivePracticalKnowledge",
    "empty_practical_knowledge_ledger",
    "entry_to_audit",
    "parse_knowledge_transmission_origin",
    "parse_practical_knowledge_kind",
    "practical_knowledge_content_key",
    "require_owner_practical_knowledge",
    "resolve_capability_anchor",
    "resolve_practical_knowledge_hop_index",
    "upsert_practical_knowledge",
    "form_or_reinforce_practical_knowledge",
    "mutate_practical_knowledge",
    "combine_practical_knowledge",
    "supersede_practical_knowledge",
    "fingerprint_jaccard_distance",
    "apply_practical_knowledge_compose",
    "apply_practical_knowledge_from_teaching",
    "apply_practical_knowledge_from_imitation",
    "apply_practical_knowledge_from_written_record",
    "apply_practical_knowledge_from_reconstruction",
    "apply_practical_knowledge_from_developmental",
    "apply_practical_knowledge_from_independent_discovery",
]


class PracticalKnowledgeKind(StrEnum):
    """Closed practical-knowledge technique kinds (not free text)."""

    FORAGING_METHOD = "foraging_method"
    HEALING_TECHNIQUE = "healing_technique"
    CRAFTING_PROCESS = "crafting_process"
    NAVIGATION_KNOWLEDGE = "navigation_knowledge"
    BUILDING_METHOD = "building_method"


# String-parity capability anchors (no private world skill-module import).
# Kind → optional SkillDomain value token for analysis joins only — never writes
# objective skills.
_CAPABILITY_ANCHOR_BY_KIND: Final[dict[PracticalKnowledgeKind, str]] = {
    PracticalKnowledgeKind.FORAGING_METHOD: "foraging",
    PracticalKnowledgeKind.HEALING_TECHNIQUE: "healing",
    PracticalKnowledgeKind.CRAFTING_PROCESS: "crafting",
    PracticalKnowledgeKind.NAVIGATION_KNOWLEDGE: "navigation",
    PracticalKnowledgeKind.BUILDING_METHOD: "building",
}


class KnowledgeTransmissionOrigin(StrEnum):
    """Closed transmission origins for practical-knowledge uptake."""

    INDEPENDENT_DISCOVERY = "independent_discovery"
    TEACHING = "teaching"
    IMITATION = "imitation"
    WRITTEN_RECORD = "written_record"
    RECONSTRUCTION = "reconstruction"
    COMBINATION = "combination"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "practical_knowledge_validation_failed field=%s reason_code=%s code=%s",
        field_name,
        code,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _require_tuple(field_name: str, values: object) -> tuple[object, ...]:
    if isinstance(values, (str, bytes, set, frozenset)) or not isinstance(
        values, Sequence
    ):
        raise _fail(field_name, "invalid_type")
    return tuple(values)


def _finite(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise _fail(field_name, "not_finite")
    return number


def _quantize_distance(value: float) -> float:
    steps = round(value / _DISTANCE_QUANTUM)
    quantized = steps * _DISTANCE_QUANTUM
    if quantized < 0.0:
        quantized = 0.0
    elif quantized > 1.0:
        quantized = 1.0
    return 0.0 if quantized == 0.0 else quantized


def parse_practical_knowledge_kind(value: object) -> PracticalKnowledgeKind:
    """Parse a closed technique kind; reject encyclopedia aliases."""
    if type(value) is PracticalKnowledgeKind:
        return value
    if not isinstance(value, str):
        raise _fail("kind", "knowledge_genealogy_kind_invalid")
    if value in _FORBIDDEN_KIND_ALIASES:
        raise _fail("kind", "forbidden_kind_alias")
    try:
        return PracticalKnowledgeKind(value)
    except ValueError as exc:
        raise _fail("kind", "knowledge_genealogy_kind_invalid") from exc


def parse_knowledge_transmission_origin(
    value: object,
) -> KnowledgeTransmissionOrigin:
    """Parse a closed transmission origin."""
    if type(value) is KnowledgeTransmissionOrigin:
        return value
    if not isinstance(value, str):
        raise _fail("origin", "knowledge_genealogy_origin_invalid")
    try:
        return KnowledgeTransmissionOrigin(value)
    except ValueError as exc:
        raise _fail("origin", "knowledge_genealogy_origin_invalid") from exc


def practical_knowledge_content_key(technique_token: str) -> str:
    """Build stable ``tech:{token}`` content key (kind-free, source-free)."""
    token = require_stable_id("technique_token", technique_token)
    if token.startswith(_CONTENT_KEY_PREFIX):
        raise _fail("technique_token", "content_key_prefix_forbidden")
    key = f"{_CONTENT_KEY_PREFIX}{token}"
    return require_stable_id("content_key", key)


def resolve_capability_anchor(kind: object) -> str | None:
    """Return optional SkillDomain value string for analysis joins (no skill write)."""
    kind_id = parse_practical_knowledge_kind(kind)
    anchor = _CAPABILITY_ANCHOR_BY_KIND.get(kind_id)
    if anchor is None:
        _LOG.debug(
            "practical_knowledge_capability_anchor kind=%s resolved=%s",
            kind_id.value,
            False,
        )
        return None
    _LOG.debug(
        "practical_knowledge_capability_anchor kind=%s resolved=%s anchor=%s",
        kind_id.value,
        True,
        anchor,
    )
    return anchor


def _normalize_fingerprint(tokens: object) -> tuple[str, ...]:
    raw = _require_tuple("content_fingerprint", tokens)
    if not raw:
        raise _fail("content_fingerprint", "empty")
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        token = require_stable_id("content_fingerprint", item)
        if token in seen:
            raise _fail("content_fingerprint", "duplicate_token")
        seen.add(token)
        out.append(token)
    return tuple(out)


@dataclass(frozen=True, slots=True)
class SubjectivePracticalKnowledge:
    """Owner-scoped practical-knowledge entry (fallible method/technique)."""

    entry_id: str
    owner_id: AgentId
    kind: PracticalKnowledgeKind
    content_key: str
    content_fingerprint: tuple[str, ...]
    origin: KnowledgeTransmissionOrigin
    parent_entry_ids: tuple[str, ...]
    lineage_root_id: str
    hop_index: int
    mutated: bool
    evidence_refs: tuple[str, ...]
    acquired_tick: int
    active: bool
    capability_anchor: str | None = None
    source_agent_id: AgentId | None = None
    teacher_agent_id: AgentId | None = None
    policy_version: str = PRACTICAL_KNOWLEDGE_POLICY_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "entry_id", require_stable_id("entry_id", self.entry_id)
        )
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        kind = parse_practical_knowledge_kind(self.kind)
        object.__setattr__(self, "kind", kind)
        key = require_stable_id("content_key", self.content_key)
        if not key.startswith(_CONTENT_KEY_PREFIX):
            raise _fail("content_key", "must_use_tech_prefix")
        object.__setattr__(self, "content_key", key)
        object.__setattr__(
            self, "content_fingerprint", _normalize_fingerprint(self.content_fingerprint)
        )
        origin = parse_knowledge_transmission_origin(self.origin)
        object.__setattr__(self, "origin", origin)

        raw_parents = _require_tuple("parent_entry_ids", self.parent_entry_ids)
        parents: list[str] = []
        seen_parents: set[str] = set()
        for item in raw_parents:
            parent_id = require_stable_id("parent_entry_ids", item)
            if parent_id == self.entry_id:
                raise _fail("parent_entry_ids", "knowledge_genealogy_cycle")
            if parent_id in seen_parents:
                raise _fail("parent_entry_ids", "duplicate_parent")
            seen_parents.add(parent_id)
            parents.append(parent_id)
        object.__setattr__(self, "parent_entry_ids", tuple(parents))

        object.__setattr__(
            self,
            "lineage_root_id",
            require_stable_id("lineage_root_id", self.lineage_root_id),
        )
        hop = require_exact_nonneg_int("hop_index", self.hop_index)
        if hop >= PRACTICAL_KNOWLEDGE_MAX_HOP_DEPTH_CEILING:
            raise _fail("hop_index", "knowledge_genealogy_hop_cap")
        object.__setattr__(self, "hop_index", hop)

        if type(self.mutated) is not bool:
            raise _fail("mutated", "invalid_type")
        if type(self.active) is not bool:
            raise _fail("active", "invalid_type")

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

        if self.capability_anchor is not None:
            object.__setattr__(
                self,
                "capability_anchor",
                require_stable_id("capability_anchor", self.capability_anchor),
            )
        if self.source_agent_id is not None and type(self.source_agent_id) is not AgentId:
            raise _fail("source_agent_id", "invalid_type")
        if (
            self.teacher_agent_id is not None
            and type(self.teacher_agent_id) is not AgentId
        ):
            raise _fail("teacher_agent_id", "invalid_type")

        if origin is KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY:
            if parents:
                # Mutation creates a child of a discovery root while retaining origin.
                if not (self.mutated and len(parents) == 1):
                    raise _fail(
                        "parent_entry_ids", "independent_discovery_no_parents"
                    )
                if hop < 1:
                    raise _fail("hop_index", "mutated_child_hop_must_be_positive")
            elif hop != PRACTICAL_KNOWLEDGE_FIRST_HOP_INDEX:
                raise _fail("hop_index", "independent_discovery_hop_must_be_zero")
        elif origin is KnowledgeTransmissionOrigin.COMBINATION:
            if len(parents) < 2:
                raise _fail(
                    "parent_entry_ids",
                    "knowledge_genealogy_combination_requires_parents",
                )
        elif origin is KnowledgeTransmissionOrigin.TEACHING:
            if self.source_agent_id is None and self.teacher_agent_id is None and not refs:
                raise _fail("evidence_refs", "teaching_provenance_required")

        acquired = require_exact_nonneg_int("acquired_tick", self.acquired_tick)
        object.__setattr__(self, "acquired_tick", acquired)
        if self.policy_version != PRACTICAL_KNOWLEDGE_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")

        _LOG.debug(
            "practical_knowledge_constructed kind=%s hop_index=%s "
            "parent_count=%s origin=%s active=%s",
            kind.value,
            hop,
            len(parents),
            origin.value,
            self.active,
        )


@dataclass(frozen=True, slots=True)
class PracticalKnowledgeLedger:
    """Private practical-knowledge ledger for one owner."""

    owner_id: AgentId
    entries: tuple[SubjectivePracticalKnowledge, ...] = ()
    policy_version: str = PRACTICAL_KNOWLEDGE_POLICY_VERSION
    max_entries: int = 64
    max_parent_ids: int = 4
    max_hop_depth: int = 16
    max_evidence_refs: int = 8

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if self.policy_version != PRACTICAL_KNOWLEDGE_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        max_entries = require_exact_nonneg_int("max_entries", self.max_entries)
        if max_entries < 1:
            raise _fail("max_entries", "out_of_range")
        object.__setattr__(self, "max_entries", max_entries)
        max_parents = require_exact_nonneg_int("max_parent_ids", self.max_parent_ids)
        if max_parents < 1:
            raise _fail("max_parent_ids", "out_of_range")
        object.__setattr__(self, "max_parent_ids", max_parents)
        max_hop = require_exact_nonneg_int("max_hop_depth", self.max_hop_depth)
        if max_hop < 1 or max_hop > PRACTICAL_KNOWLEDGE_MAX_HOP_DEPTH_CEILING:
            raise _fail("max_hop_depth", "out_of_range")
        object.__setattr__(self, "max_hop_depth", max_hop)
        max_refs = require_exact_nonneg_int("max_evidence_refs", self.max_evidence_refs)
        if max_refs < 1:
            raise _fail("max_evidence_refs", "out_of_range")
        object.__setattr__(self, "max_evidence_refs", max_refs)

        raw = _require_tuple("entries", self.entries)
        checked: list[SubjectivePracticalKnowledge] = []
        seen_ids: set[str] = set()
        active_keys: set[str] = set()
        for item in raw:
            if type(item) is not SubjectivePracticalKnowledge:
                raise _fail("entries", "invalid_type")
            if item.owner_id != self.owner_id:
                raise _fail("entries", "owner_mismatch")
            if item.entry_id in seen_ids:
                raise _fail("entries", "duplicate_entry_id")
            seen_ids.add(item.entry_id)
            if len(item.parent_entry_ids) > max_parents:
                raise _fail("parent_entry_ids", "knowledge_genealogy_parent_cap")
            if item.hop_index >= max_hop:
                raise _fail("hop_index", "knowledge_genealogy_hop_cap")
            if len(item.evidence_refs) > max_refs:
                raise _fail("evidence_refs", "evidence_ref_cap")
            if item.active:
                if item.content_key in active_keys:
                    raise _fail("entries", "duplicate_active_content_key")
                active_keys.add(item.content_key)
            checked.append(item)
        if len(checked) > max_entries:
            raise _fail("entries", "max_entries_exceeded")
        _assert_owner_local_acyclic(checked)
        object.__setattr__(self, "entries", tuple(checked))


@dataclass(frozen=True, slots=True)
class PracticalKnowledgeAudit:
    """Metadata-only practical-knowledge audit row (analysis harvest)."""

    owner_id: AgentId
    entry_id: str
    kind: str
    content_key: str
    origin: str
    parent_entry_ids: tuple[str, ...]
    lineage_root_id: str
    hop_index: int
    mutated: bool
    acquired_tick: int
    tick: int
    active: bool
    reason_code: str
    fingerprint_distance_q: float = 0.0
    source_agent_id: str | None = None
    teacher_agent_id: str | None = None
    capability_anchor: str | None = None

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        object.__setattr__(
            self, "entry_id", require_stable_id("entry_id", self.entry_id)
        )
        kind = parse_practical_knowledge_kind(self.kind)
        object.__setattr__(self, "kind", kind.value)
        object.__setattr__(
            self, "content_key", require_stable_id("content_key", self.content_key)
        )
        origin = parse_knowledge_transmission_origin(self.origin)
        object.__setattr__(self, "origin", origin.value)
        raw_parents = _require_tuple("parent_entry_ids", self.parent_entry_ids)
        parents = tuple(
            require_stable_id("parent_entry_ids", item) for item in raw_parents
        )
        object.__setattr__(self, "parent_entry_ids", parents)
        object.__setattr__(
            self,
            "lineage_root_id",
            require_stable_id("lineage_root_id", self.lineage_root_id),
        )
        object.__setattr__(
            self, "hop_index", require_exact_nonneg_int("hop_index", self.hop_index)
        )
        if type(self.mutated) is not bool:
            raise _fail("mutated", "invalid_type")
        if type(self.active) is not bool:
            raise _fail("active", "invalid_type")
        object.__setattr__(
            self,
            "acquired_tick",
            require_exact_nonneg_int("acquired_tick", self.acquired_tick),
        )
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))
        object.__setattr__(
            self, "reason_code", require_stable_id("reason_code", self.reason_code)
        )
        distance = _quantize_distance(_finite("fingerprint_distance_q", self.fingerprint_distance_q))
        if distance < 0.0 or distance > 1.0:
            raise _fail("fingerprint_distance_q", "out_of_range")
        object.__setattr__(self, "fingerprint_distance_q", distance)
        if self.source_agent_id is not None:
            object.__setattr__(
                self,
                "source_agent_id",
                require_stable_id("source_agent_id", self.source_agent_id),
            )
        if self.teacher_agent_id is not None:
            object.__setattr__(
                self,
                "teacher_agent_id",
                require_stable_id("teacher_agent_id", self.teacher_agent_id),
            )
        if self.capability_anchor is not None:
            object.__setattr__(
                self,
                "capability_anchor",
                require_stable_id("capability_anchor", self.capability_anchor),
            )


def empty_practical_knowledge_ledger(
    owner_id: AgentId,
    *,
    max_entries: int = 64,
    max_parent_ids: int = 4,
    max_hop_depth: int = 16,
    max_evidence_refs: int = 8,
) -> PracticalKnowledgeLedger:
    """Return an empty owner practical-knowledge ledger (channel may be on)."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    ledger = PracticalKnowledgeLedger(
        owner_id=owner_id,
        max_entries=max_entries,
        max_parent_ids=max_parent_ids,
        max_hop_depth=max_hop_depth,
        max_evidence_refs=max_evidence_refs,
    )
    _LOG.debug(
        "practical_knowledge_ledger_empty owner_id=%s entry_count=%s",
        owner_id.value,
        0,
    )
    return ledger


def require_owner_practical_knowledge(
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
    if type(ledger) is not PracticalKnowledgeLedger:
        _LOG.warning("practical_knowledge_carry_rejected reason=%s", "invalid_type")
        raise TypeError(f"{field_name} must be PracticalKnowledgeLedger")
    if ledger.owner_id != owner_id:
        _LOG.error(
            "practical_knowledge_validation_failed field=%s reason_code=%s",
            field_name,
            "owner_mismatch",
        )
        _LOG.warning("practical_knowledge_carry_rejected reason=%s", "owner_mismatch")
        raise ValueError(f"{field_name} owner_id mismatch")


def entry_to_audit(
    entry: SubjectivePracticalKnowledge,
    *,
    tick: int,
    reason_code: str,
    fingerprint_distance_q: float = 0.0,
) -> PracticalKnowledgeAudit:
    """Build a metadata-only audit from an entry (no fingerprint payloads)."""
    if type(entry) is not SubjectivePracticalKnowledge:
        raise _fail("entry", "invalid_type")
    return PracticalKnowledgeAudit(
        owner_id=entry.owner_id,
        entry_id=entry.entry_id,
        kind=entry.kind.value,
        content_key=entry.content_key,
        origin=entry.origin.value,
        parent_entry_ids=entry.parent_entry_ids,
        lineage_root_id=entry.lineage_root_id,
        hop_index=entry.hop_index,
        mutated=entry.mutated,
        source_agent_id=(
            None if entry.source_agent_id is None else entry.source_agent_id.value
        ),
        teacher_agent_id=(
            None if entry.teacher_agent_id is None else entry.teacher_agent_id.value
        ),
        capability_anchor=entry.capability_anchor,
        acquired_tick=entry.acquired_tick,
        tick=tick,
        active=entry.active,
        reason_code=reason_code,
        fingerprint_distance_q=fingerprint_distance_q,
    )


def _entry_by_id(
    ledger: PracticalKnowledgeLedger, entry_id: str
) -> SubjectivePracticalKnowledge | None:
    for entry in ledger.entries:
        if entry.entry_id == entry_id:
            return entry
    return None


def _assert_owner_local_acyclic(
    entries: Sequence[SubjectivePracticalKnowledge],
) -> None:
    by_id = {entry.entry_id: entry for entry in entries}
    visiting: set[str] = set()
    visited: set[str] = set()

    def walk(node_id: str) -> None:
        if node_id in visited:
            return
        if node_id in visiting:
            raise _fail("parent_entry_ids", "knowledge_genealogy_cycle")
        visiting.add(node_id)
        node = by_id.get(node_id)
        if node is not None:
            for parent_id in node.parent_entry_ids:
                if parent_id in by_id:
                    walk(parent_id)
        visiting.remove(node_id)
        visited.add(node_id)

    for entry in entries:
        walk(entry.entry_id)


def resolve_practical_knowledge_hop_index(
    ledger: PracticalKnowledgeLedger,
    *,
    origin: KnowledgeTransmissionOrigin | object,
    parent_entry_ids: Sequence[str],
    parent_hop_index: int | None = None,
) -> int:
    """Resolve owner-local hop index; missing parent without hint ⇒ hop 1."""
    origin_id = parse_knowledge_transmission_origin(origin)
    if origin_id is KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY:
        return PRACTICAL_KNOWLEDGE_FIRST_HOP_INDEX
    parents = tuple(parent_entry_ids)
    if not parents:
        # Peer-taught / imitation / written_record uptake: empty parents ⇒ hop 1.
        return 1
    hops: list[int] = []
    for parent_id in parents:
        parent = _entry_by_id(ledger, require_stable_id("parent_entry_ids", parent_id))
        if parent is not None:
            hops.append(parent.hop_index)
        elif parent_hop_index is not None:
            hops.append(
                require_exact_nonneg_int("parent_hop_index", parent_hop_index)
            )
        else:
            # Evicted / missing owner-local parent ⇒ hop 1 (not 0).
            hops.append(1)
    return max(hops) + 1


def _evict_entries(
    entries: Sequence[SubjectivePracticalKnowledge],
    *,
    max_entries: int,
    owner_id: AgentId,
) -> list[SubjectivePracticalKnowledge]:
    if len(entries) <= max_entries:
        return list(entries)
    # Evict inactive first, then oldest by (acquired_tick, entry_id).
    ordered = sorted(
        entries,
        key=lambda row: (row.active, row.acquired_tick, row.entry_id),
    )
    drop_count = len(ordered) - max_entries
    kept = ordered[drop_count:]
    _LOG.debug(
        "practical_knowledge_evict owner_id=%s dropped=%s reason_code=%s",
        owner_id.value,
        drop_count,
        "max_entries_evict",
    )
    return kept


def upsert_practical_knowledge(
    ledger: PracticalKnowledgeLedger,
    entry: SubjectivePracticalKnowledge,
) -> PracticalKnowledgeLedger:
    """Insert or replace an entry by ``entry_id`` with deterministic eviction."""
    if type(ledger) is not PracticalKnowledgeLedger:
        raise _fail("ledger", "invalid_type")
    if type(entry) is not SubjectivePracticalKnowledge:
        raise _fail("entry", "invalid_type")
    if entry.owner_id != ledger.owner_id:
        raise _fail("entry", "owner_mismatch")
    if len(entry.parent_entry_ids) > ledger.max_parent_ids:
        raise _fail("parent_entry_ids", "knowledge_genealogy_parent_cap")
    if entry.hop_index >= ledger.max_hop_depth:
        raise _fail("hop_index", "knowledge_genealogy_hop_cap")
    if len(entry.evidence_refs) > ledger.max_evidence_refs:
        raise _fail("evidence_refs", "evidence_ref_cap")

    rows: list[SubjectivePracticalKnowledge] = []
    replaced = False
    for row in ledger.entries:
        if row.entry_id == entry.entry_id:
            rows.append(entry)
            replaced = True
        elif entry.active and row.active and row.content_key == entry.content_key:
            # Soft-supersede prior active row sharing content_key.
            rows.append(
                SubjectivePracticalKnowledge(
                    entry_id=row.entry_id,
                    owner_id=row.owner_id,
                    kind=row.kind,
                    content_key=row.content_key,
                    content_fingerprint=row.content_fingerprint,
                    capability_anchor=row.capability_anchor,
                    origin=row.origin,
                    parent_entry_ids=row.parent_entry_ids,
                    lineage_root_id=row.lineage_root_id,
                    hop_index=row.hop_index,
                    mutated=row.mutated,
                    source_agent_id=row.source_agent_id,
                    teacher_agent_id=row.teacher_agent_id,
                    evidence_refs=row.evidence_refs,
                    acquired_tick=row.acquired_tick,
                    active=False,
                )
            )
        else:
            rows.append(row)
    if not replaced:
        rows.append(entry)
    rows = _evict_entries(
        rows, max_entries=ledger.max_entries, owner_id=ledger.owner_id
    )
    result = PracticalKnowledgeLedger(
        owner_id=ledger.owner_id,
        entries=tuple(rows),
        policy_version=ledger.policy_version,
        max_entries=ledger.max_entries,
        max_parent_ids=ledger.max_parent_ids,
        max_hop_depth=ledger.max_hop_depth,
        max_evidence_refs=ledger.max_evidence_refs,
    )
    _LOG.debug(
        "practical_knowledge_upsert owner_id=%s kind=%s origin=%s "
        "hop_index=%s parent_count=%s active=%s reason_code=%s",
        ledger.owner_id.value,
        entry.kind.value,
        entry.origin.value,
        entry.hop_index,
        len(entry.parent_entry_ids),
        entry.active,
        "upsert",
    )
    return result


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


def fingerprint_jaccard_distance(
    left: Sequence[str], right: Sequence[str]
) -> float:
    """Return ``1 - jaccard`` over fingerprint token sets."""
    left_set = set(_normalize_fingerprint(left))
    right_set = set(_normalize_fingerprint(right))
    if not left_set or not right_set:
        return 1.0
    union = left_set | right_set
    return 1.0 - (len(left_set & right_set) / len(union))


def _active_by_content_key(
    ledger: PracticalKnowledgeLedger, content_key: str
) -> SubjectivePracticalKnowledge | None:
    for entry in ledger.entries:
        if entry.active and entry.content_key == content_key:
            return entry
    return None


def _lineage_root_for(
    *,
    owner_id: AgentId,
    kind: PracticalKnowledgeKind,
    content_key: str,
    origin: KnowledgeTransmissionOrigin,
    parents: Sequence[SubjectivePracticalKnowledge],
    source_agent_id: AgentId | None,
) -> str:
    if parents:
        return parents[0].lineage_root_id
    source = source_agent_id.value if source_agent_id is not None else owner_id.value
    if origin is KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY:
        source = owner_id.value
    return require_stable_id(
        "lineage_root_id",
        f"root:{source}:{kind.value}:{content_key}",
    )


def _require_channel_active(channel_active: bool) -> None:
    if type(channel_active) is not bool:
        raise TypeError("channel_active must be bool")
    if not channel_active:
        raise _fail("knowledge_genealogy", "knowledge_genealogy_inactive")


def form_or_reinforce_practical_knowledge(
    ledger: PracticalKnowledgeLedger,
    *,
    kind: object,
    content_key: str,
    content_fingerprint: Sequence[str],
    origin: object,
    tick: int,
    enabled_kinds: Sequence[str],
    parent_entry_ids: Sequence[str] = (),
    evidence_refs: Sequence[str] = (),
    parent_hop_index: int | None = None,
    capability_anchor: str | None = None,
    source_agent_id: AgentId | None = None,
    teacher_agent_id: AgentId | None = None,
    entry_id: str | None = None,
    channel_active: bool = True,
) -> PracticalKnowledgeLedger:
    """Form a new active entry or reinforce the active row for ``content_key``.

    Library API: no live loop trigger required. Peer-taught uptake may use empty
    owner-local parents with public ``source_agent_id`` / evidence refs.
    """
    _require_channel_active(channel_active)
    if type(ledger) is not PracticalKnowledgeLedger:
        raise _fail("ledger", "invalid_type")
    kind_id = parse_practical_knowledge_kind(kind)
    enabled = {parse_practical_knowledge_kind(item).value for item in enabled_kinds}
    if kind_id.value not in enabled:
        raise _fail("kind", "kind_not_enabled")
    origin_id = parse_knowledge_transmission_origin(origin)
    key = require_stable_id("content_key", content_key)
    if not key.startswith(_CONTENT_KEY_PREFIX):
        key = practical_knowledge_content_key(key)
    fingerprint = _normalize_fingerprint(content_fingerprint)
    tick_i = require_exact_nonneg_int("tick", tick)
    parents = tuple(
        require_stable_id("parent_entry_ids", item) for item in parent_entry_ids
    )
    if len(parents) > ledger.max_parent_ids:
        raise _fail("parent_entry_ids", "knowledge_genealogy_parent_cap")
    if origin_id is KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY and parents:
        raise _fail("parent_entry_ids", "independent_discovery_no_parents")
    if origin_id is KnowledgeTransmissionOrigin.COMBINATION and len(parents) < 2:
        raise _fail(
            "parent_entry_ids", "knowledge_genealogy_combination_requires_parents"
        )

    refs = _cap_evidence_refs(evidence_refs, max_refs=ledger.max_evidence_refs)
    existing = _active_by_content_key(ledger, key)
    if existing is not None:
        merged_refs = _cap_evidence_refs(
            [*existing.evidence_refs, *refs], max_refs=ledger.max_evidence_refs
        )
        reinforced = SubjectivePracticalKnowledge(
            entry_id=existing.entry_id,
            owner_id=ledger.owner_id,
            kind=existing.kind,
            content_key=existing.content_key,
            content_fingerprint=fingerprint,
            capability_anchor=existing.capability_anchor,
            origin=existing.origin,
            parent_entry_ids=existing.parent_entry_ids,
            lineage_root_id=existing.lineage_root_id,
            hop_index=existing.hop_index,
            mutated=existing.mutated,
            source_agent_id=existing.source_agent_id,
            teacher_agent_id=existing.teacher_agent_id,
            evidence_refs=merged_refs,
            acquired_tick=existing.acquired_tick,
            active=True,
        )
        result = upsert_practical_knowledge(ledger, reinforced)
        _LOG.info(
            "practical_knowledge_reinforce entry_id=%s origin=%s hop_index=%s "
            "mutated=%s",
            reinforced.entry_id,
            reinforced.origin.value,
            reinforced.hop_index,
            reinforced.mutated,
        )
        return result

    hop = resolve_practical_knowledge_hop_index(
        ledger,
        origin=origin_id,
        parent_entry_ids=parents,
        parent_hop_index=parent_hop_index,
    )
    if hop >= ledger.max_hop_depth:
        raise _fail("hop_index", "knowledge_genealogy_hop_cap")

    parent_rows = []
    for parent_id in parents:
        parent = _entry_by_id(ledger, parent_id)
        if parent is None:
            continue
        parent_rows.append(parent)
        # Owner-local cycle: refuse if new id would point into ancestor of itself
        # once assigned; checked on upsert via ledger edges.

    if entry_id is None:
        entry_id = (
            f"pk:{ledger.owner_id.value}:{kind_id.value}:{key}:h{hop}:t{tick_i}"
        )
    root = _lineage_root_for(
        owner_id=ledger.owner_id,
        kind=kind_id,
        content_key=key,
        origin=origin_id,
        parents=parent_rows,
        source_agent_id=source_agent_id,
    )
    teacher = teacher_agent_id
    if origin_id is KnowledgeTransmissionOrigin.TEACHING and teacher is None:
        teacher = source_agent_id
    formed = SubjectivePracticalKnowledge(
        entry_id=entry_id,
        owner_id=ledger.owner_id,
        kind=kind_id,
        content_key=key,
        content_fingerprint=fingerprint,
        capability_anchor=capability_anchor,
        origin=origin_id,
        parent_entry_ids=parents,
        lineage_root_id=root,
        hop_index=hop,
        mutated=False,
        source_agent_id=source_agent_id,
        teacher_agent_id=teacher,
        evidence_refs=refs,
        acquired_tick=tick_i,
        active=True,
    )
    result = upsert_practical_knowledge(ledger, formed)
    _LOG.info(
        "practical_knowledge_form entry_id=%s origin=%s hop_index=%s mutated=%s",
        formed.entry_id,
        formed.origin.value,
        formed.hop_index,
        False,
    )
    return result


def mutate_practical_knowledge(
    ledger: PracticalKnowledgeLedger,
    *,
    entry_id: str,
    tick: int,
    allow_mutation: bool,
    mutation_requires_evidence: bool,
    owner_evidence_present: bool,
    max_token_edits: int,
    mutation_distance_threshold: float,
    rng_namespace: str,
    seed_material: str = "0",
    channel_active: bool = True,
) -> PracticalKnowledgeLedger:
    """Create a **new child** entry mutated from ``entry_id`` (library API).

    Prior entry stays as an owner-local parent; same ``content_key`` soft-supersedes
    the prior active row via upsert. No live loop trigger required.
    """
    _require_channel_active(channel_active)
    if type(ledger) is not PracticalKnowledgeLedger:
        raise _fail("ledger", "invalid_type")
    if not allow_mutation:
        raise _fail("mutation_policy", "knowledge_genealogy_mutation_disabled")
    if mutation_requires_evidence and not owner_evidence_present:
        _LOG.debug(
            "practical_knowledge_mutation_skip owner_id=%s reason_code=%s",
            ledger.owner_id.value,
            "mutation_requires_evidence",
        )
        raise _fail("evidence_refs", "mutation_requires_evidence")
    token = require_stable_id("entry_id", entry_id)
    tick_i = require_exact_nonneg_int("tick", tick)
    edits = require_exact_nonneg_int("max_token_edits", max_token_edits)
    if edits > 8:
        raise _fail("max_token_edits", "out_of_range")
    threshold = _finite("mutation_distance_threshold", mutation_distance_threshold)
    if threshold <= 0.0 or threshold > 1.0:
        raise _fail("mutation_distance_threshold", "out_of_range")
    namespace = require_stable_id("rng_namespace", rng_namespace)
    seed = require_stable_id("seed_material", str(seed_material))
    prior = _entry_by_id(ledger, token)
    if prior is None:
        raise _fail("entry_id", "unknown_entry")
    child_hop = prior.hop_index + 1
    if child_hop >= ledger.max_hop_depth:
        raise _fail("hop_index", "knowledge_genealogy_hop_cap")

    tokens = list(prior.content_fingerprint)
    edit_count = min(edits, len(tokens))
    material = f"{namespace}:{seed}:{token}:{tick_i}"
    for index in range(edit_count):
        pick = int(
            hashlib.sha256(f"{material}:pick:{index}".encode()).hexdigest(), 16
        )
        target = pick % len(tokens)
        replacement = hashlib.sha256(
            f"{material}:edit:{index}:{tokens[target]}".encode()
        ).hexdigest()[:8]
        tokens[target] = require_stable_id("content_fingerprint", replacement)
    child_fp = tuple(tokens)
    distance = fingerprint_jaccard_distance(prior.content_fingerprint, child_fp)
    mutated_flag = distance >= threshold
    child_id = f"pkmut:{ledger.owner_id.value}:{token}:t{tick_i}"
    child = SubjectivePracticalKnowledge(
        entry_id=child_id,
        owner_id=ledger.owner_id,
        kind=prior.kind,
        content_key=prior.content_key,
        content_fingerprint=child_fp,
        capability_anchor=prior.capability_anchor,
        origin=prior.origin,
        parent_entry_ids=(prior.entry_id,),
        lineage_root_id=prior.lineage_root_id,
        hop_index=child_hop,
        mutated=mutated_flag,
        source_agent_id=prior.source_agent_id,
        teacher_agent_id=prior.teacher_agent_id,
        evidence_refs=prior.evidence_refs,
        acquired_tick=tick_i,
        active=True,
    )
    result = upsert_practical_knowledge(ledger, child)
    _LOG.info(
        "practical_knowledge_mutate entry_id=%s origin=%s hop_index=%s mutated=%s",
        child.entry_id,
        child.origin.value,
        child.hop_index,
        child.mutated,
    )
    return result


def combine_practical_knowledge(
    ledger: PracticalKnowledgeLedger,
    *,
    parent_entry_ids: Sequence[str],
    tick: int,
    allow_combination: bool,
    allow_multi_parent: bool,
    min_token_overlap: float,
    require_combination_distinct_roots: bool = False,
    enabled_kinds: Sequence[str] | None = None,
    channel_active: bool = True,
) -> PracticalKnowledgeLedger:
    """Combine ≥2 owner-local parents into a new ``combination`` entry (library API)."""
    _require_channel_active(channel_active)
    if type(ledger) is not PracticalKnowledgeLedger:
        raise _fail("ledger", "invalid_type")
    if not allow_combination:
        raise _fail("mutation_policy", "knowledge_genealogy_combination_disabled")
    if not allow_multi_parent:
        raise _fail("lineage_policy", "knowledge_genealogy_combination_disabled")
    ordered_ids = tuple(
        require_stable_id("parent_entry_ids", item) for item in parent_entry_ids
    )
    if len(ordered_ids) < 2:
        raise _fail(
            "parent_entry_ids", "knowledge_genealogy_combination_requires_parents"
        )
    if len(ordered_ids) > ledger.max_parent_ids:
        raise _fail("parent_entry_ids", "knowledge_genealogy_parent_cap")
    if len(set(ordered_ids)) != len(ordered_ids):
        raise _fail("parent_entry_ids", "duplicate_parent")

    parents: list[SubjectivePracticalKnowledge] = []
    for parent_id in ordered_ids:
        parent = _entry_by_id(ledger, parent_id)
        if parent is None:
            raise _fail("parent_entry_ids", "unknown_parent")
        parents.append(parent)

    kind = parents[0].kind
    if any(parent.kind is not kind for parent in parents):
        raise _fail("kind", "combination_kind_mismatch")
    if enabled_kinds is not None:
        enabled = {parse_practical_knowledge_kind(item).value for item in enabled_kinds}
        if kind.value not in enabled:
            raise _fail("kind", "kind_not_enabled")
    if require_combination_distinct_roots:
        roots = {parent.lineage_root_id for parent in parents}
        if len(roots) < 2:
            raise _fail("lineage_root_id", "combination_requires_distinct_roots")

    overlap_floor = _finite("min_token_overlap", min_token_overlap)
    if overlap_floor < 0.0 or overlap_floor > 1.0:
        raise _fail("min_token_overlap", "out_of_range")
    # Pairwise token overlap floor against first parent.
    base_tokens = set(parents[0].content_fingerprint)
    for parent in parents[1:]:
        other = set(parent.content_fingerprint)
        if not base_tokens or not other:
            raise _fail("content_fingerprint", "combination_overlap_insufficient")
        overlap = len(base_tokens & other) / len(base_tokens | other)
        if overlap < overlap_floor:
            raise _fail("content_fingerprint", "combination_overlap_insufficient")

    tick_i = require_exact_nonneg_int("tick", tick)
    hop = max(parent.hop_index for parent in parents) + 1
    if hop >= ledger.max_hop_depth:
        raise _fail("hop_index", "knowledge_genealogy_hop_cap")

    token_parts = sorted(
        parent.content_key[len(_CONTENT_KEY_PREFIX) :] for parent in parents
    )
    joined = "+".join(token_parts)
    if len(joined) > 96:
        joined = hashlib.sha256(joined.encode()).hexdigest()[:24]
    content_key = practical_knowledge_content_key(joined)
    merged_fp: list[str] = []
    seen_fp: set[str] = set()
    for parent in parents:
        for token in parent.content_fingerprint:
            if token not in seen_fp:
                seen_fp.add(token)
                merged_fp.append(token)
    child_id = f"pkcomb:{ledger.owner_id.value}:{content_key}:t{tick_i}"
    child = SubjectivePracticalKnowledge(
        entry_id=child_id,
        owner_id=ledger.owner_id,
        kind=kind,
        content_key=content_key,
        content_fingerprint=tuple(merged_fp),
        capability_anchor=parents[0].capability_anchor,
        origin=KnowledgeTransmissionOrigin.COMBINATION,
        parent_entry_ids=ordered_ids,
        lineage_root_id=parents[0].lineage_root_id,
        hop_index=hop,
        mutated=False,
        source_agent_id=None,
        teacher_agent_id=None,
        evidence_refs=_cap_evidence_refs(
            [ref for parent in parents for ref in parent.evidence_refs],
            max_refs=ledger.max_evidence_refs,
        ),
        acquired_tick=tick_i,
        active=True,
    )
    result = upsert_practical_knowledge(ledger, child)
    _LOG.info(
        "practical_knowledge_combine entry_id=%s origin=%s hop_index=%s "
        "mutated=%s parent_count=%s",
        child.entry_id,
        child.origin.value,
        child.hop_index,
        False,
        len(ordered_ids),
    )
    return result


def supersede_practical_knowledge(
    ledger: PracticalKnowledgeLedger,
    *,
    entry_id: str,
    tick: int,
    channel_active: bool = True,
) -> PracticalKnowledgeLedger:
    """Soft-forget an entry (``active=False``) without DELETE."""
    _require_channel_active(channel_active)
    if type(ledger) is not PracticalKnowledgeLedger:
        raise _fail("ledger", "invalid_type")
    token = require_stable_id("entry_id", entry_id)
    require_exact_nonneg_int("tick", tick)
    prior = _entry_by_id(ledger, token)
    if prior is None:
        raise _fail("entry_id", "unknown_entry")
    if not prior.active:
        return ledger
    superseded = SubjectivePracticalKnowledge(
        entry_id=prior.entry_id,
        owner_id=prior.owner_id,
        kind=prior.kind,
        content_key=prior.content_key,
        content_fingerprint=prior.content_fingerprint,
        capability_anchor=prior.capability_anchor,
        origin=prior.origin,
        parent_entry_ids=prior.parent_entry_ids,
        lineage_root_id=prior.lineage_root_id,
        hop_index=prior.hop_index,
        mutated=prior.mutated,
        source_agent_id=prior.source_agent_id,
        teacher_agent_id=prior.teacher_agent_id,
        evidence_refs=prior.evidence_refs,
        acquired_tick=prior.acquired_tick,
        active=False,
    )
    result = upsert_practical_knowledge(ledger, superseded)
    _LOG.info(
        "practical_knowledge_supersede entry_id=%s origin=%s hop_index=%s "
        "mutated=%s",
        superseded.entry_id,
        superseded.origin.value,
        superseded.hop_index,
        superseded.mutated,
    )
    return result


_ADVICE_DOMAIN_TO_KIND: Final[dict[str, PracticalKnowledgeKind]] = {
    "foraging": PracticalKnowledgeKind.FORAGING_METHOD,
    "healing": PracticalKnowledgeKind.HEALING_TECHNIQUE,
    "crafting": PracticalKnowledgeKind.CRAFTING_PROCESS,
    "navigation": PracticalKnowledgeKind.NAVIGATION_KNOWLEDGE,
    "building": PracticalKnowledgeKind.BUILDING_METHOD,
}
_SKIP_ADVICE_DOMAINS: Final[frozenset[str]] = frozenset(
    {"resource_detection", "communication", "teaching"}
)
_MENTORSHIP_CONTENT_TO_KIND: Final[dict[str, PracticalKnowledgeKind]] = {
    "production_recipes": PracticalKnowledgeKind.CRAFTING_PROCESS,
}
_OCCURRENCE_KIND_HINTS: Final[tuple[tuple[str, PracticalKnowledgeKind], ...]] = (
    ("forag", PracticalKnowledgeKind.FORAGING_METHOD),
    ("heal", PracticalKnowledgeKind.HEALING_TECHNIQUE),
    ("craft", PracticalKnowledgeKind.CRAFTING_PROCESS),
    ("navig", PracticalKnowledgeKind.NAVIGATION_KNOWLEDGE),
    ("build", PracticalKnowledgeKind.BUILDING_METHOD),
)
_WRITTEN_GENRE_TO_KIND: Final[dict[str, PracticalKnowledgeKind]] = {
    "instruction": PracticalKnowledgeKind.CRAFTING_PROCESS,
    "inventory": PracticalKnowledgeKind.FORAGING_METHOD,
    "recipe": PracticalKnowledgeKind.CRAFTING_PROCESS,
}


def _technique_token(raw: str) -> str:
    cleaned = "".join(
        ch if (ch.isalnum() or ch in "-_") else "-" for ch in str(raw).lower()
    ).strip("-_")
    if not cleaned:
        cleaned = "technique"
    # Collapse runs of dashes for stable-id friendliness.
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return require_stable_id("technique_token", cleaned[:64])


def _kind_from_occurrence(kind_raw: str) -> PracticalKnowledgeKind | None:
    lowered = str(kind_raw).lower()
    for hint, kind in _OCCURRENCE_KIND_HINTS:
        if hint in lowered:
            return kind
    return None


def _agent_id_or_none(value: object) -> AgentId | None:
    if type(value) is AgentId:
        return value
    token = getattr(value, "value", None)
    if isinstance(token, str):
        try:
            return AgentId(token)
        except (TypeError, ValueError):
            return None
    return None


def _try_form(
    ledger: PracticalKnowledgeLedger,
    *,
    kind: PracticalKnowledgeKind,
    technique_token: str,
    fingerprint: Sequence[str],
    origin: KnowledgeTransmissionOrigin,
    tick: int,
    enabled_kinds: Sequence[str],
    evidence_refs: Sequence[str] = (),
    source_agent_id: AgentId | None = None,
    teacher_agent_id: AgentId | None = None,
) -> tuple[PracticalKnowledgeLedger, PracticalKnowledgeAudit | None]:
    content_key = practical_knowledge_content_key(technique_token)
    prior = _active_by_content_key(ledger, content_key)
    try:
        updated = form_or_reinforce_practical_knowledge(
            ledger,
            kind=kind,
            content_key=content_key,
            content_fingerprint=fingerprint,
            origin=origin,
            tick=tick,
            enabled_kinds=enabled_kinds,
            evidence_refs=evidence_refs,
            capability_anchor=resolve_capability_anchor(kind),
            source_agent_id=source_agent_id,
            teacher_agent_id=teacher_agent_id,
        )
    except ValueError as exc:
        message = str(exc)
        if "knowledge_genealogy_hop_cap" in message or "kind_not_enabled" in message:
            _LOG.debug(
                "practical_knowledge_compose origin=%s skip_reason=%s",
                origin.value,
                "hop_cap" if "hop_cap" in message else "kind_not_enabled",
            )
            return ledger, None
        raise
    entry = _active_by_content_key(updated, content_key)
    if entry is None:
        return updated, None
    reason = "reinforced" if prior is not None else "formed"
    return updated, entry_to_audit(entry, tick=tick, reason_code=reason)


def apply_practical_knowledge_from_teaching(
    ledger: PracticalKnowledgeLedger,
    *,
    enabled_kinds: Sequence[str],
    advice_delta: Sequence[object],
    tick: int,
    teaching_compose_on: bool,
    teaching_mode_on: bool,
    mentorship_channel_on: bool = False,
) -> tuple[PracticalKnowledgeLedger, tuple[PracticalKnowledgeAudit, ...]]:
    """Map teaching/mentorship public advice onto technique entries (no peer copy)."""
    if type(ledger) is not PracticalKnowledgeLedger:
        raise _fail("ledger", "invalid_type")
    if not teaching_compose_on:
        return ledger, ()
    if not teaching_mode_on and not mentorship_channel_on:
        _LOG.debug(
            "practical_knowledge_compose origin=%s skip_reason=%s",
            KnowledgeTransmissionOrigin.TEACHING.value,
            "teaching_mode_off",
        )
        return ledger, ()
    if not advice_delta:
        return ledger, ()
    current = ledger
    audits: list[PracticalKnowledgeAudit] = []
    for row in advice_delta:
        teacher = _agent_id_or_none(getattr(row, "source_agent_id", None))
        domain = getattr(getattr(row, "domain", None), "value", None)
        if not isinstance(domain, str):
            domain = None
        content_kind = getattr(getattr(row, "content_kind", None), "value", None)
        if not isinstance(content_kind, str):
            content_kind = None
        if domain in _SKIP_ADVICE_DOMAINS:
            _LOG.debug(
                "practical_knowledge_compose origin=%s skip_reason=%s",
                KnowledgeTransmissionOrigin.TEACHING.value,
                f"domain_skipped:{domain}",
            )
            continue
        kind = None
        token = None
        if domain is not None:
            kind = _ADVICE_DOMAIN_TO_KIND.get(domain)
            token = domain
        if kind is None and content_kind is not None:
            kind = _MENTORSHIP_CONTENT_TO_KIND.get(content_kind)
            token = content_kind
        if kind is None or token is None:
            _LOG.debug(
                "practical_knowledge_compose origin=%s skip_reason=%s",
                KnowledgeTransmissionOrigin.TEACHING.value,
                "unmapped_teaching_domain",
            )
            continue
        occurrence = getattr(row, "occurrence_id", None) or "teach"
        evidence = [f"teach:{occurrence}"]
        if mentorship_channel_on and teacher is not None:
            evidence.append(f"mentor:{teacher.value}")
        band = getattr(getattr(row, "band", None), "value", "unspecified")
        current, audit = _try_form(
            current,
            kind=kind,
            technique_token=_technique_token(token),
            fingerprint=(f"cue:teach:{token}", f"band:{band}"),
            origin=KnowledgeTransmissionOrigin.TEACHING,
            tick=tick,
            enabled_kinds=enabled_kinds,
            evidence_refs=tuple(evidence),
            source_agent_id=teacher,
            teacher_agent_id=teacher,
        )
        if audit is not None:
            audits.append(audit)
            _LOG.debug(
                "practical_knowledge_compose origin=%s skip_reason=%s",
                KnowledgeTransmissionOrigin.TEACHING.value,
                "ok",
            )
    return current, tuple(audits)


def apply_practical_knowledge_from_imitation(
    ledger: PracticalKnowledgeLedger,
    *,
    enabled_kinds: Sequence[str],
    observation: object | None,
    tick: int,
    imitation_compose_on: bool,
) -> tuple[PracticalKnowledgeLedger, tuple[PracticalKnowledgeAudit, ...]]:
    """Uptake from colocated successful practice (never embeds peer id in content_key)."""
    if type(ledger) is not PracticalKnowledgeLedger:
        raise _fail("ledger", "invalid_type")
    if not imitation_compose_on:
        return ledger, ()
    if observation is None:
        _LOG.debug(
            "practical_knowledge_compose origin=%s skip_reason=%s",
            KnowledgeTransmissionOrigin.IMITATION.value,
            "observation_absent",
        )
        return ledger, ()
    current = ledger
    audits: list[PracticalKnowledgeAudit] = []
    for occurrence in getattr(observation, "occurrences", ()) or ():
        kind_raw = str(getattr(occurrence, "kind", "")).lower()
        other = getattr(occurrence, "other_entity_id", None)
        success = getattr(occurrence, "success", None)
        if other is None:
            continue
        if success is not True and "success" not in kind_raw and "complete" not in kind_raw:
            continue
        kind = _kind_from_occurrence(kind_raw)
        if kind is None:
            continue
        other_token = other.value if hasattr(other, "value") else str(other)
        event_id = getattr(getattr(occurrence, "provenance", None), "event_id", None)
        evidence_token = (
            f"evt:{event_id.value}"
            if event_id is not None and hasattr(event_id, "value")
            else f"occ:{tick}:{kind_raw}"
        )
        # content_key must not embed peer id — technique token from occurrence kind only.
        current, audit = _try_form(
            current,
            kind=kind,
            technique_token=_technique_token(kind_raw),
            fingerprint=(f"cue:imit:{kind_raw}",),
            origin=KnowledgeTransmissionOrigin.IMITATION,
            tick=tick,
            enabled_kinds=enabled_kinds,
            evidence_refs=(evidence_token, f"actor:{other_token}"),
            source_agent_id=None,
        )
        if audit is not None:
            audits.append(audit)
    return current, tuple(audits)


def apply_practical_knowledge_from_written_record(
    ledger: PracticalKnowledgeLedger,
    *,
    enabled_kinds: Sequence[str],
    observation: object | None,
    artifact_interpretations: object | None,
    tick: int,
    written_compose_on: bool,
    artifacts_on: bool,
    durable_on: bool,
    repositories_on: bool,
) -> tuple[PracticalKnowledgeLedger, tuple[PracticalKnowledgeAudit, ...]]:
    """Uptake from durable artifact / repository perception cues (marks ≠ truth)."""
    if type(ledger) is not PracticalKnowledgeLedger:
        raise _fail("ledger", "invalid_type")
    if not written_compose_on:
        return ledger, ()
    if not artifacts_on and not durable_on and not repositories_on:
        _LOG.debug(
            "practical_knowledge_compose origin=%s skip_reason=%s",
            KnowledgeTransmissionOrigin.WRITTEN_RECORD.value,
            "artifacts_off",
        )
        return ledger, ()
    current = ledger
    audits: list[PracticalKnowledgeAudit] = []

    if artifacts_on or durable_on:
        entries = ()
        if artifact_interpretations is not None:
            entries = (
                getattr(artifact_interpretations, "interpretations", None)
                or getattr(artifact_interpretations, "entries", None)
                or ()
            )
        for entry in entries:
            artifact_id = (
                getattr(entry, "artifact_id", None)
                or getattr(entry, "mark_id", None)
                or getattr(entry, "entity_id", None)
            )
            aid = getattr(artifact_id, "value", artifact_id)
            if not isinstance(aid, str):
                continue
            genre = getattr(entry, "record_genre", None)
            genre_token = getattr(genre, "value", genre)
            if not isinstance(genre_token, str):
                genre_token = "instruction"
            kind = _WRITTEN_GENRE_TO_KIND.get(genre_token, PracticalKnowledgeKind.CRAFTING_PROCESS)
            author = _agent_id_or_none(
                getattr(entry, "author_id", None)
                or getattr(entry, "source_agent_id", None)
            )
            current, audit = _try_form(
                current,
                kind=kind,
                technique_token=_technique_token(f"mark-{aid}"),
                fingerprint=(f"cue:mark:{aid}", f"genre:{genre_token}"),
                origin=KnowledgeTransmissionOrigin.WRITTEN_RECORD,
                tick=tick,
                enabled_kinds=enabled_kinds,
                evidence_refs=(f"artifact:{aid}",),
                source_agent_id=author,
            )
            if audit is not None:
                audits.append(audit)

        for artifact in getattr(observation, "artifacts", ()) or () if observation else ():
            genre = getattr(artifact, "record_genre", None)
            genre_token = getattr(genre, "value", None)
            if not isinstance(genre_token, str):
                continue
            kind = _WRITTEN_GENRE_TO_KIND.get(genre_token)
            if kind is None:
                continue
            aid = getattr(getattr(artifact, "artifact_id", None), "value", None) or getattr(
                getattr(artifact, "entity_id", None), "value", None
            )
            if not isinstance(aid, str):
                aid = f"art-{tick}-{genre_token}"
            author = _agent_id_or_none(getattr(artifact, "author_id", None))
            current, audit = _try_form(
                current,
                kind=kind,
                technique_token=_technique_token(f"durable-{aid}"),
                fingerprint=(f"cue:durable:{aid}", f"genre:{genre_token}"),
                origin=KnowledgeTransmissionOrigin.WRITTEN_RECORD,
                tick=tick,
                enabled_kinds=enabled_kinds,
                evidence_refs=(f"durable:{aid}",),
                source_agent_id=author,
            )
            if audit is not None:
                audits.append(audit)

    if repositories_on and observation is not None:
        for repository in getattr(observation, "repositories", ()) or ():
            repo_id = getattr(repository, "repository_id", None)
            repo_token = getattr(repo_id, "value", None)
            if not isinstance(repo_token, str):
                continue
            access = getattr(repository, "access", "retrieve")
            current, audit = _try_form(
                current,
                kind=PracticalKnowledgeKind.CRAFTING_PROCESS,
                technique_token=_technique_token(f"repo-{repo_token}"),
                fingerprint=(f"cue:repo:{repo_token}", f"access:{access}"),
                origin=KnowledgeTransmissionOrigin.WRITTEN_RECORD,
                tick=tick,
                enabled_kinds=enabled_kinds,
                evidence_refs=(f"repo:{repo_token}",),
            )
            if audit is not None:
                audits.append(audit)
    return current, tuple(audits)


def apply_practical_knowledge_from_reconstruction(
    ledger: PracticalKnowledgeLedger,
    *,
    enabled_kinds: Sequence[str],
    observation: object | None,
    tick: int,
    reconstruction_compose_on: bool,
    reconstructive_memory_on: bool,
) -> tuple[PracticalKnowledgeLedger, tuple[PracticalKnowledgeAudit, ...]]:
    """Rebuild incomplete technique cues when reconstructive memory path is on."""
    if type(ledger) is not PracticalKnowledgeLedger:
        raise _fail("ledger", "invalid_type")
    if not reconstruction_compose_on:
        return ledger, ()
    if not reconstructive_memory_on:
        _LOG.debug(
            "practical_knowledge_compose origin=%s skip_reason=%s",
            KnowledgeTransmissionOrigin.RECONSTRUCTION.value,
            "reconstructive_memory_off",
        )
        return ledger, ()
    if observation is None:
        return ledger, ()
    current = ledger
    audits: list[PracticalKnowledgeAudit] = []
    for occurrence in getattr(observation, "occurrences", ()) or ():
        kind_raw = str(getattr(occurrence, "kind", "")).lower()
        if "recall" not in kind_raw and "reconstruct" not in kind_raw and "partial" not in kind_raw:
            continue
        kind = _kind_from_occurrence(kind_raw) or PracticalKnowledgeKind.FORAGING_METHOD
        current, audit = _try_form(
            current,
            kind=kind,
            technique_token=_technique_token(f"recon-{kind_raw}"),
            fingerprint=(f"cue:recon:{kind_raw}", "incomplete"),
            origin=KnowledgeTransmissionOrigin.RECONSTRUCTION,
            tick=tick,
            enabled_kinds=enabled_kinds,
            evidence_refs=(f"recon:{tick}:{kind_raw}",),
        )
        if audit is not None:
            audits.append(audit)
    return current, tuple(audits)


def apply_practical_knowledge_from_developmental(
    ledger: PracticalKnowledgeLedger,
    *,
    enabled_kinds: Sequence[str],
    developmental_audits: Sequence[object],
    tick: int,
    developmental_compose_on: bool,
    developmental_channel_on: bool,
) -> tuple[PracticalKnowledgeLedger, tuple[PracticalKnowledgeAudit, ...]]:
    """Compose from developmental SKILLS / PRACTICES acquisition audits."""
    if type(ledger) is not PracticalKnowledgeLedger:
        raise _fail("ledger", "invalid_type")
    if not developmental_compose_on:
        return ledger, ()
    if not developmental_channel_on:
        _LOG.debug(
            "practical_knowledge_compose origin=%s skip_reason=%s",
            "developmental",
            "developmental_channel_off",
        )
        return ledger, ()
    current = ledger
    audits: list[PracticalKnowledgeAudit] = []
    for row in developmental_audits:
        domain = getattr(row, "domain_id", None) or getattr(row, "domain", None)
        domain_token = getattr(domain, "value", domain)
        if domain_token not in {"skills", "practices"}:
            continue
        concept = getattr(row, "concept_key", None)
        if not isinstance(concept, str):
            continue
        kind = _kind_from_occurrence(concept) or PracticalKnowledgeKind.FORAGING_METHOD
        teacher = _agent_id_or_none(getattr(row, "teacher_agent_id", None))
        evidence = getattr(row, "evidence_ref", None) or f"dev:{concept}"
        # Developmental compose uses teaching origin when a teacher is present,
        # otherwise independent_discovery-style root via reconstruction-adjacent
        # developmental path recorded as imitation-free independent when no teacher.
        origin = (
            KnowledgeTransmissionOrigin.TEACHING
            if teacher is not None
            else KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY
        )
        # Plan lists developmental as compose flag; origin stays independent when
        # self-acquired, teaching when instructed — never combination/mutation here.
        if teacher is None:
            origin = KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY
        current, audit = _try_form(
            current,
            kind=kind,
            technique_token=_technique_token(concept.replace(":", "-")),
            fingerprint=(f"cue:dev:{concept}",),
            origin=origin,
            tick=tick,
            enabled_kinds=enabled_kinds,
            evidence_refs=(str(evidence),),
            source_agent_id=teacher,
            teacher_agent_id=teacher,
        )
        if audit is not None:
            audits.append(audit)
    return current, tuple(audits)


def apply_practical_knowledge_from_independent_discovery(
    ledger: PracticalKnowledgeLedger,
    *,
    enabled_kinds: Sequence[str],
    observation: object | None,
    tick: int,
    independent_compose_on: bool,
) -> tuple[PracticalKnowledgeLedger, tuple[PracticalKnowledgeAudit, ...]]:
    """Mint independent roots from own successful practice / experimentation."""
    if type(ledger) is not PracticalKnowledgeLedger:
        raise _fail("ledger", "invalid_type")
    if not independent_compose_on:
        return ledger, ()
    if observation is None:
        return ledger, ()
    current = ledger
    audits: list[PracticalKnowledgeAudit] = []
    for occurrence in getattr(observation, "occurrences", ()) or ():
        kind_raw = str(getattr(occurrence, "kind", "")).lower()
        other = getattr(occurrence, "other_entity_id", None)
        success = getattr(occurrence, "success", None)
        if other is not None:
            continue
        if success is not True and "experiment" not in kind_raw and "discover" not in kind_raw:
            continue
        kind = _kind_from_occurrence(kind_raw)
        if kind is None:
            continue
        event_id = getattr(getattr(occurrence, "provenance", None), "event_id", None)
        evidence_token = (
            f"evt:{event_id.value}"
            if event_id is not None and hasattr(event_id, "value")
            else f"occ:{tick}:{kind_raw}"
        )
        current, audit = _try_form(
            current,
            kind=kind,
            technique_token=_technique_token(kind_raw),
            fingerprint=(f"cue:discover:{kind_raw}",),
            origin=KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY,
            tick=tick,
            enabled_kinds=enabled_kinds,
            evidence_refs=(evidence_token,),
        )
        if audit is not None:
            audits.append(audit)
    return current, tuple(audits)


def apply_practical_knowledge_compose(
    ledger: PracticalKnowledgeLedger,
    *,
    enabled_kinds: Sequence[str],
    tick: int,
    uptake_compose: object,
    observation: object | None = None,
    advice_delta: Sequence[object] = (),
    artifact_interpretations: object | None = None,
    developmental_audits: Sequence[object] = (),
    teaching_mode_on: bool = False,
    mentorship_channel_on: bool = False,
    artifacts_on: bool = False,
    durable_on: bool = False,
    repositories_on: bool = False,
    reconstructive_memory_on: bool = False,
    developmental_channel_on: bool = False,
) -> tuple[PracticalKnowledgeLedger, tuple[PracticalKnowledgeAudit, ...]]:
    """Run all uptake compose adapters gated by ``uptake_compose`` flags."""
    if type(ledger) is not PracticalKnowledgeLedger:
        raise _fail("ledger", "invalid_type")
    if uptake_compose is None:
        return ledger, ()
    current = ledger
    audits: list[PracticalKnowledgeAudit] = []

    current, rows = apply_practical_knowledge_from_teaching(
        current,
        enabled_kinds=enabled_kinds,
        advice_delta=advice_delta,
        tick=tick,
        teaching_compose_on=bool(getattr(uptake_compose, "teaching", False)),
        teaching_mode_on=teaching_mode_on,
        mentorship_channel_on=mentorship_channel_on,
    )
    audits.extend(rows)

    current, rows = apply_practical_knowledge_from_imitation(
        current,
        enabled_kinds=enabled_kinds,
        observation=observation,
        tick=tick,
        imitation_compose_on=bool(getattr(uptake_compose, "imitation", False)),
    )
    audits.extend(rows)

    current, rows = apply_practical_knowledge_from_written_record(
        current,
        enabled_kinds=enabled_kinds,
        observation=observation,
        artifact_interpretations=artifact_interpretations,
        tick=tick,
        written_compose_on=bool(getattr(uptake_compose, "written_record", False)),
        artifacts_on=artifacts_on,
        durable_on=durable_on,
        repositories_on=repositories_on,
    )
    audits.extend(rows)

    current, rows = apply_practical_knowledge_from_reconstruction(
        current,
        enabled_kinds=enabled_kinds,
        observation=observation,
        tick=tick,
        reconstruction_compose_on=bool(
            getattr(uptake_compose, "reconstruction", False)
        ),
        reconstructive_memory_on=reconstructive_memory_on,
    )
    audits.extend(rows)

    current, rows = apply_practical_knowledge_from_developmental(
        current,
        enabled_kinds=enabled_kinds,
        developmental_audits=developmental_audits,
        tick=tick,
        developmental_compose_on=bool(getattr(uptake_compose, "developmental", False)),
        developmental_channel_on=developmental_channel_on,
    )
    audits.extend(rows)

    current, rows = apply_practical_knowledge_from_independent_discovery(
        current,
        enabled_kinds=enabled_kinds,
        observation=observation,
        tick=tick,
        independent_compose_on=bool(
            getattr(uptake_compose, "independent_discovery", False)
        ),
    )
    audits.extend(rows)

    return current, tuple(audits)
