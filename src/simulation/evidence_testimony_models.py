"""Canonical ``evidence-testimony-snapshot-v1`` records and bounded document.

The snapshot is an independent analytical sibling. It carries no owner id, no
witness identity, no payload body, no confidence value beyond a closed band, and
no forbidden truth-like field.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, fields
from typing import Any, Final, NoReturn

__all__ = [
    "EVIDENCE_TESTIMONY_ARTIFACT_ERROR_CODES",
    "EVIDENCE_TESTIMONY_CANDIDATE_CONTRADICTIONS_MAX",
    "EVIDENCE_TESTIMONY_CANDIDATE_ITEMS_MAX",
    "EVIDENCE_TESTIMONY_PORT_ERROR_CODES",
    "EVIDENCE_TESTIMONY_SNAPSHOT_MAX_BYTES",
    "EVIDENCE_TESTIMONY_SNAPSHOT_POLICY_VERSION",
    "EVIDENCE_TESTIMONY_SNAPSHOT_SCHEMA",
    "EVIDENCE_TESTIMONY_SUPPORTED_SCHEMAS",
    "EvidenceCandidateRecord",
    "EvidenceContradictionRecord",
    "EvidenceCustodyRecord",
    "EvidenceEvaluationRecord",
    "EvidenceItemRecord",
    "EvidenceLineageEdgeRecord",
    "EvidenceObjectiveRow",
    "EvidenceSourceRecord",
    "EvidenceTestimonyArtifactError",
    "EvidenceTestimonyCounts",
    "EvidenceTestimonyCoverage",
    "EvidenceTestimonyRecord",
    "EvidenceTestimonySnapshot",
    "EvidenceTestimonySnapshotRef",
    "EvidenceWindowRecord",
    "empty_evidence_testimony_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.evidence_testimony_models")

EVIDENCE_TESTIMONY_SNAPSHOT_SCHEMA: Final[str] = "evidence-testimony-snapshot-v1"
EVIDENCE_TESTIMONY_SNAPSHOT_POLICY_VERSION: Final[str] = (
    "evidence-testimony-analysis.v1"
)
EVIDENCE_TESTIMONY_SUPPORTED_SCHEMAS: Final[tuple[str, ...]] = (
    EVIDENCE_TESTIMONY_SNAPSHOT_SCHEMA,
)

EVIDENCE_CANDIDATE_PREFIX: Final[str] = "evid-"
EVIDENCE_ITEM_PREFIX: Final[str] = "evid-item-"
EVIDENCE_EDGE_PREFIX: Final[str] = "evid-edge-"
EVIDENCE_PUBLICATION_PREFIX: Final[str] = "evid-pub-"
_OWNER_LOCAL_PREFIXES: Final[tuple[str, ...]] = (
    "evs-",
    "evw-",
    "evi-",
    "evc-",
    "evx-",
    "eva-",
)
_FORBIDDEN_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "truth",
        "verified",
        "authenticated",
        "authentic",
        "forged",
        "fake",
        "proof",
        "verdict",
        "guilt",
        "guilty",
        "liable",
        "liability",
        "true_owner",
        "winner",
    }
)

EVIDENCE_TESTIMONY_SNAPSHOT_MAX_BYTES: Final[int] = 4 * 1024 * 1024
EVIDENCE_TESTIMONY_MAX_CANDIDATES: Final[int] = 2048
EVIDENCE_TESTIMONY_MAX_SOURCES: Final[int] = 8192
EVIDENCE_TESTIMONY_MAX_TESTIMONY: Final[int] = 8192
EVIDENCE_TESTIMONY_MAX_ITEMS: Final[int] = 16384
EVIDENCE_TESTIMONY_MAX_CUSTODY: Final[int] = 16384
EVIDENCE_TESTIMONY_MAX_CONTRADICTIONS: Final[int] = 8192
EVIDENCE_TESTIMONY_MAX_EVALUATIONS: Final[int] = 16384
EVIDENCE_TESTIMONY_MAX_WINDOWS: Final[int] = 512
EVIDENCE_TESTIMONY_MAX_OBJECTIVE_ROWS: Final[int] = 4096
EVIDENCE_TESTIMONY_CANDIDATE_ITEMS_MAX: Final[int] = 64
EVIDENCE_TESTIMONY_CANDIDATE_CONTRADICTIONS_MAX: Final[int] = 32
EVIDENCE_TESTIMONY_PAGE_MAX_BYTES: Final[int] = 2 * 1024 * 1024
EVIDENCE_TESTIMONY_PAGE_MAX_ROWS: Final[int] = 500

EVIDENCE_TESTIMONY_ARTIFACT_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "evidence_testimony_invalid_snapshot",
        "evidence_testimony_digest_mismatch",
        "evidence_testimony_size_limit",
        "evidence_testimony_not_found",
        "evidence_testimony_publication_exists",
    }
)
EVIDENCE_TESTIMONY_PORT_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "evidence_testimony_not_found",
        "evidence_testimony_cursor_invalid",
        "evidence_testimony_cursor_expired",
        "evidence_testimony_disabled",
        "evidence_testimony_size_limit",
    }
)


class EvidenceTestimonyArtifactError(ValueError):
    """Stable-code snapshot violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if code not in EVIDENCE_TESTIMONY_ARTIFACT_ERROR_CODES:
            raise ValueError("evidence_testimony_invalid_error_code")
        self.code = code
        super().__init__(code)


def _fail(code: str) -> NoReturn:
    raise EvidenceTestimonyArtifactError(code)


class EvidenceTestimonyCoverage:
    """Closed coverage tokens for one published snapshot."""

    COMPLETE: Final[str] = "complete"
    PARTIAL: Final[str] = "partial"
    TOKENS: Final[frozenset[str]] = frozenset({COMPLETE, PARTIAL})


@dataclass(frozen=True, slots=True)
class EvidenceTestimonySnapshotRef:
    """Portable reference to one published snapshot."""

    run_id: str
    publication_id: str
    snapshot_digest: str

    def __post_init__(self) -> None:
        if type(self.run_id) is not str or not self.run_id:
            _fail("evidence_testimony_invalid_snapshot")
        if type(self.publication_id) is not str or not self.publication_id.startswith(
            EVIDENCE_PUBLICATION_PREFIX
        ):
            _fail("evidence_testimony_invalid_snapshot")
        if type(self.snapshot_digest) is not str or len(self.snapshot_digest) != 64:
            _fail("evidence_testimony_invalid_snapshot")


def _reject_forbidden(model: type[Any]) -> None:
    for field in fields(model):
        if field.name in _FORBIDDEN_FIELDS:
            _fail("evidence_testimony_invalid_snapshot")


def _text(value: object, *, max_len: int = 128) -> str:
    if not isinstance(value, str) or not value or len(value) > max_len:
        _fail("evidence_testimony_invalid_snapshot")
    return value


def _optional_text(value: object, *, max_len: int = 128) -> str | None:
    if value is None:
        return None
    return _text(value, max_len=max_len)


def _tick(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail("evidence_testimony_invalid_snapshot")
    return value


def _count(value: object) -> int:
    return _tick(value)


def _digest(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def evidence_row_id(prefix: str, *parts: object) -> str:
    """Mint one deterministic analytical record id."""

    return prefix + _digest(prefix, *(str(part) for part in parts))[:16]


@dataclass(frozen=True, slots=True)
class EvidenceTestimonyRecord:
    """Shared owner-row validation for snapshot records."""

    owner_token: str
    local_id: str
    tick: int

    def _validate(self) -> None:
        _reject_forbidden(type(self))
        if type(self.owner_token) is not str or len(self.owner_token) != 16:
            _fail("evidence_testimony_invalid_snapshot")
        if not self.local_id.startswith(_OWNER_LOCAL_PREFIXES):
            _fail("evidence_testimony_invalid_snapshot")
        _tick(self.tick)


@dataclass(frozen=True, slots=True)
class EvidenceSourceRecord(EvidenceTestimonyRecord):
    source_kind: str
    reference_kind: str
    provenance: str
    confidence_band: str
    subject_token: str
    custody_status: str = "unknown"
    root_ref: str | None = None
    correlation_token: str | None = None

    def __post_init__(self) -> None:
        self._validate()
        _text(self.source_kind)
        _text(self.reference_kind)
        _text(self.provenance)
        if self.confidence_band not in {"low", "mid", "high"}:
            _fail("evidence_testimony_invalid_snapshot")
        _text(self.subject_token)
        if self.custody_status not in {
            "not_applicable",
            "complete_belief",
            "incomplete_belief",
            "conflicting_belief",
            "unknown",
        }:
            _fail("evidence_testimony_invalid_snapshot")
        _optional_text(self.root_ref)
        _optional_text(self.correlation_token)


@dataclass(frozen=True, slots=True)
class EvidenceTestimonyRecordRow(EvidenceTestimonyRecord):
    speaker_token: str
    subject_token: str
    channel: str
    confidence_band: str
    root_ref: str | None = None

    def __post_init__(self) -> None:
        self._validate()
        _text(self.speaker_token)
        _text(self.subject_token)
        if self.channel not in {"direct", "communicated"}:
            _fail("evidence_testimony_invalid_snapshot")
        if self.confidence_band not in {"low", "mid", "high"}:
            _fail("evidence_testimony_invalid_snapshot")
        _optional_text(self.root_ref)


@dataclass(frozen=True, slots=True)
class EvidenceItemRecord(EvidenceTestimonyRecord):
    candidate_id: str
    subject_token: str
    interpretation: str
    confidence_band: str
    status: str
    anchor_local_id: str = ""

    def __post_init__(self) -> None:
        self._validate()
        if not self.candidate_id.startswith(EVIDENCE_CANDIDATE_PREFIX):
            _fail("evidence_testimony_invalid_snapshot")
        _text(self.subject_token)
        _text(self.interpretation)
        if self.confidence_band not in {"low", "mid", "high"}:
            _fail("evidence_testimony_invalid_snapshot")
        if self.status not in {"active", "retracted", "superseded"}:
            _fail("evidence_testimony_invalid_snapshot")
        if self.anchor_local_id:
            _text(self.anchor_local_id)


@dataclass(frozen=True, slots=True)
class EvidenceCustodyRecord(EvidenceTestimonyRecord):
    source_local_id: str
    role: str
    holder_token: str | None = None
    custodian_token: str | None = None
    location_token: str | None = None

    def __post_init__(self) -> None:
        self._validate()
        _text(self.source_local_id)
        if self.role not in {
            "holder",
            "repository_custodian",
            "location",
            "observer",
        }:
            _fail("evidence_testimony_invalid_snapshot")
        _optional_text(self.holder_token)
        _optional_text(self.custodian_token)
        _optional_text(self.location_token)


@dataclass(frozen=True, slots=True)
class EvidenceContradictionRecord(EvidenceTestimonyRecord):
    candidate_id: str
    first_ref: str
    second_ref: str
    kind: str
    status: str

    def __post_init__(self) -> None:
        self._validate()
        if not self.candidate_id.startswith(EVIDENCE_CANDIDATE_PREFIX):
            _fail("evidence_testimony_invalid_snapshot")
        if self.first_ref == self.second_ref:
            _fail("evidence_testimony_invalid_snapshot")
        _text(self.first_ref)
        _text(self.second_ref)
        _text(self.kind)
        if self.status not in {
            "unresolved",
            "owner_prefers_first",
            "owner_prefers_second",
            "withdrawn",
        }:
            _fail("evidence_testimony_invalid_snapshot")


@dataclass(frozen=True, slots=True)
class EvidenceEvaluationRecord(EvidenceTestimonyRecord):
    item_ref: str
    bases: tuple[str, ...]
    kind: str
    confidence_band: str

    def __post_init__(self) -> None:
        self._validate()
        _text(self.item_ref)
        if isinstance(self.bases, (str, bytes)) or not isinstance(
            self.bases, (tuple, list)
        ):
            _fail("evidence_testimony_invalid_snapshot")
        bases = tuple(sorted({_text(item) for item in self.bases}))
        if not bases:
            _fail("evidence_testimony_invalid_snapshot")
        object.__setattr__(self, "bases", bases)
        _text(self.kind)
        if self.confidence_band not in {"low", "mid", "high"}:
            _fail("evidence_testimony_invalid_snapshot")


@dataclass(frozen=True, slots=True)
class EvidenceCandidateRecord:
    candidate_id: str
    subject_token: str
    source_kind_family: str
    owner_tokens: tuple[str, ...]
    item_count: int
    source_count: int
    testimony_count: int
    contradiction_count: int
    status: str
    coverage: str
    first_tick: int
    last_tick: int
    creation_digest: str

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        if not self.candidate_id.startswith(EVIDENCE_CANDIDATE_PREFIX):
            _fail("evidence_testimony_invalid_snapshot")
        _text(self.subject_token)
        _text(self.source_kind_family)
        owners = tuple(sorted({_text(item, max_len=16) for item in self.owner_tokens}))
        if not owners:
            _fail("evidence_testimony_invalid_snapshot")
        object.__setattr__(self, "owner_tokens", owners)
        for name in (
            "item_count",
            "source_count",
            "testimony_count",
            "contradiction_count",
            "first_tick",
            "last_tick",
        ):
            _count(getattr(self, name))
        if self.status not in {
            "convergent",
            "contested",
            "fragmented",
            "isolated",
            "unknown",
        }:
            _fail("evidence_testimony_invalid_snapshot")
        if self.coverage not in EvidenceTestimonyCoverage.TOKENS:
            _fail("evidence_testimony_invalid_snapshot")
        if len(self.creation_digest) != 64:
            _fail("evidence_testimony_invalid_snapshot")


@dataclass(frozen=True, slots=True)
class EvidenceObjectiveRow:
    anchor_id: str
    kind: str
    tick: int
    actor_token: str | None = None
    target_token: str | None = None
    subject_token: str | None = None
    quantity: int = 0
    correlation_token: str | None = None

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        if not self.anchor_id.startswith(EVIDENCE_CANDIDATE_PREFIX):
            _fail("evidence_testimony_invalid_snapshot")
        _text(self.kind)
        _tick(self.tick)
        _count(self.quantity)
        _optional_text(self.actor_token)
        _optional_text(self.target_token)
        _optional_text(self.subject_token)
        _optional_text(self.correlation_token)


@dataclass(frozen=True, slots=True)
class EvidenceWindowRecord:
    window_index: int
    start_tick: int
    end_tick: int
    source_count: int
    testimony_count: int
    item_count: int
    contradiction_count: int
    evaluation_count: int
    objective_anchor_count: int
    partial: bool

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        for name in (
            "window_index",
            "start_tick",
            "end_tick",
            "source_count",
            "testimony_count",
            "item_count",
            "contradiction_count",
            "evaluation_count",
            "objective_anchor_count",
        ):
            _count(getattr(self, name))
        if self.end_tick < self.start_tick:
            _fail("evidence_testimony_invalid_snapshot")
        if type(self.partial) is not bool:
            _fail("evidence_testimony_invalid_snapshot")


@dataclass(frozen=True, slots=True)
class EvidenceLineageEdgeRecord:
    edge_id: str
    kind: str
    source_ids: tuple[str, ...]
    target_ids: tuple[str, ...]
    window_index: int

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        if not self.edge_id.startswith(EVIDENCE_EDGE_PREFIX):
            _fail("evidence_testimony_invalid_snapshot")
        _text(self.kind)
        if not self.source_ids and not self.target_ids:
            _fail("evidence_testimony_invalid_snapshot")
        for item in (*self.source_ids, *self.target_ids):
            _text(item)
        _count(self.window_index)


@dataclass(frozen=True, slots=True)
class EvidenceTestimonyCounts:
    candidate_count: int = 0
    source_count: int = 0
    testimony_count: int = 0
    item_count: int = 0
    custody_link_count: int = 0
    contradiction_count: int = 0
    evaluation_count: int = 0
    edge_count: int = 0
    window_count: int = 0

    def __post_init__(self) -> None:
        for field in fields(type(self)):
            _count(getattr(self, field.name))


def _ordered(value: object) -> tuple[object, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        _fail("evidence_testimony_invalid_snapshot")
    return tuple(value)


@dataclass(frozen=True, slots=True)
class EvidenceTestimonySnapshot:
    """One bounded canonical evidence-testimony snapshot."""

    run_id: str
    generated_tick: int
    candidates: tuple[EvidenceCandidateRecord, ...] = ()
    sources: tuple[EvidenceSourceRecord, ...] = ()
    testimony: tuple[EvidenceTestimonyRecordRow, ...] = ()
    items: tuple[EvidenceItemRecord, ...] = ()
    custody: tuple[EvidenceCustodyRecord, ...] = ()
    contradictions: tuple[EvidenceContradictionRecord, ...] = ()
    evaluations: tuple[EvidenceEvaluationRecord, ...] = ()
    objective_rows: tuple[EvidenceObjectiveRow, ...] = ()
    windows: tuple[EvidenceWindowRecord, ...] = ()
    edges: tuple[EvidenceLineageEdgeRecord, ...] = ()
    counts: EvidenceTestimonyCounts = EvidenceTestimonyCounts()
    coverage: str = EvidenceTestimonyCoverage.COMPLETE
    policy_version: str = EVIDENCE_TESTIMONY_SNAPSHOT_POLICY_VERSION
    schema_version: str = EVIDENCE_TESTIMONY_SNAPSHOT_SCHEMA
    snapshot_digest: str = ""
    publication_id: str = ""

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        if self.schema_version not in EVIDENCE_TESTIMONY_SUPPORTED_SCHEMAS:
            _fail("evidence_testimony_invalid_snapshot")
        if self.policy_version != EVIDENCE_TESTIMONY_SNAPSHOT_POLICY_VERSION:
            _fail("evidence_testimony_invalid_snapshot")
        if self.coverage not in EvidenceTestimonyCoverage.TOKENS:
            _fail("evidence_testimony_invalid_snapshot")
        _text(self.run_id)
        _tick(self.generated_tick)
        limits = (
            ("candidates", EVIDENCE_TESTIMONY_MAX_CANDIDATES, "candidate_id"),
            ("sources", EVIDENCE_TESTIMONY_MAX_SOURCES, "local_id"),
            ("testimony", EVIDENCE_TESTIMONY_MAX_TESTIMONY, "local_id"),
            ("items", EVIDENCE_TESTIMONY_MAX_ITEMS, "local_id"),
            ("custody", EVIDENCE_TESTIMONY_MAX_CUSTODY, "local_id"),
            ("contradictions", EVIDENCE_TESTIMONY_MAX_CONTRADICTIONS, "local_id"),
            ("evaluations", EVIDENCE_TESTIMONY_MAX_EVALUATIONS, "local_id"),
            ("objective_rows", EVIDENCE_TESTIMONY_MAX_OBJECTIVE_ROWS, "anchor_id"),
            ("windows", EVIDENCE_TESTIMONY_MAX_WINDOWS, "window_index"),
            ("edges", EVIDENCE_TESTIMONY_MAX_ITEMS, "edge_id"),
        )
        for name, limit, id_field in limits:
            collection = _ordered(getattr(self, name))
            if len(collection) > limit:
                _fail("evidence_testimony_size_limit")
            seen: set[object] = set()
            for row in collection:
                identifier = getattr(row, id_field)
                if identifier in seen:
                    _fail("evidence_testimony_invalid_snapshot")
                seen.add(identifier)
            ordered = tuple(sorted(collection, key=lambda row: getattr(row, id_field)))
            object.__setattr__(self, name, ordered)

        candidate_ids = {row.candidate_id for row in self.candidates}
        source_ids = {row.local_id for row in self.sources}
        testimony_ids = {row.local_id for row in self.testimony}
        item_ids = {row.local_id for row in self.items}
        custody_ids = {row.local_id for row in self.custody}
        item_refs = source_ids | testimony_ids | item_ids | custody_ids

        for row in self.sources:
            if row.local_id.startswith("evid-"):
                _fail("evidence_testimony_invalid_snapshot")
        for row in self.testimony:
            if row.local_id.startswith("evid-"):
                _fail("evidence_testimony_invalid_snapshot")
        for row in self.items:
            if row.local_id.startswith("evid-"):
                _fail("evidence_testimony_invalid_snapshot")
            if row.candidate_id not in candidate_ids:
                _fail("evidence_testimony_invalid_snapshot")
            if row.anchor_local_id and row.anchor_local_id not in item_refs:
                _fail("evidence_testimony_invalid_snapshot")
        for row in self.custody:
            if row.local_id.startswith("evid-"):
                _fail("evidence_testimony_invalid_snapshot")
            if row.source_local_id not in source_ids:
                _fail("evidence_testimony_invalid_snapshot")
        for row in self.contradictions:
            if row.local_id.startswith("evid-"):
                _fail("evidence_testimony_invalid_snapshot")
            if row.candidate_id not in candidate_ids:
                _fail("evidence_testimony_invalid_snapshot")
            if row.first_ref not in item_refs or row.second_ref not in item_refs:
                _fail("evidence_testimony_invalid_snapshot")
        for row in self.evaluations:
            if row.local_id.startswith("evid-"):
                _fail("evidence_testimony_invalid_snapshot")
            if row.item_ref not in item_ids:
                _fail("evidence_testimony_invalid_snapshot")
        for row in self.objective_rows:
            if row.actor_token is not None and row.actor_token in source_ids:
                _fail("evidence_testimony_invalid_snapshot")
        for row in self.candidates:
            items = [
                item for item in self.items if item.candidate_id == row.candidate_id
            ]
            contradictions = [
                item
                for item in self.contradictions
                if item.candidate_id == row.candidate_id
            ]
            if len(items) > EVIDENCE_TESTIMONY_CANDIDATE_ITEMS_MAX:
                _fail("evidence_testimony_size_limit")
            if len(contradictions) > EVIDENCE_TESTIMONY_CANDIDATE_CONTRADICTIONS_MAX:
                _fail("evidence_testimony_size_limit")
        ticks = [row.start_tick for row in self.windows]
        if len(ticks) != len(set(ticks)):
            _fail("evidence_testimony_invalid_snapshot")

        self._validate_acyclic()
        if not self.counts == EvidenceTestimonyCounts(
            candidate_count=len(self.candidates),
            source_count=len(self.sources),
            testimony_count=len(self.testimony),
            item_count=len(self.items),
            custody_link_count=len(self.custody),
            contradiction_count=len(self.contradictions),
            evaluation_count=len(self.evaluations),
            edge_count=len(self.edges),
            window_count=len(self.windows),
        ):
            _fail("evidence_testimony_invalid_snapshot")
        if self.snapshot_digest and (
            type(self.snapshot_digest) is not str or len(self.snapshot_digest) != 64
        ):
            _fail("evidence_testimony_invalid_snapshot")
        if self.publication_id and not self.publication_id.startswith(
            EVIDENCE_PUBLICATION_PREFIX
        ):
            _fail("evidence_testimony_invalid_snapshot")
        _LOG.debug(
            "evidence_testimony_snapshot_bounded candidates=%s sources=%s",
            len(self.candidates),
            len(self.sources),
        )

    def _validate_acyclic(self) -> None:
        edges = {row.edge_id: row for row in self.edges}
        adjacency: dict[str, set[str]] = {}
        for row in edges.values():
            for source in row.source_ids:
                adjacency.setdefault(source, set()).update(row.target_ids)
        visiting: set[str] = set()
        settled: set[str] = set()

        def visit(node: str) -> None:
            if node in settled:
                return
            if node in visiting:
                _fail("evidence_testimony_invalid_snapshot")
            visiting.add(node)
            for target in adjacency.get(node, ()):
                visit(target)
            visiting.discard(node)
            settled.add(node)

        for node in sorted(adjacency):
            visit(node)


def empty_evidence_testimony_snapshot(
    run_id: str, *, generated_tick: int
) -> EvidenceTestimonySnapshot:
    """Return one enabled-but-empty canonical snapshot."""

    return EvidenceTestimonySnapshot(run_id=run_id, generated_tick=generated_tick)
