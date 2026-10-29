"""Strict physical index contracts for bounded lineage publications.

``lineage-store-index-v2`` is a physical layout, separate from the logical
``lineage-snapshot-v1`` projection. Fixed-purpose roots reference bounded,
authenticated index pages; no root keeps one digest per descendant object.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from simulation.lineage_codec import LINEAGE_RECORD_MAX_BYTES
from simulation.lineage_identity import LineageEvidenceClass, LineageFamily
from simulation.lineage_models import (
    LineageCoverage,
    LineageCoverageState,
    LineageError,
)
from simulation.models import RunId
from world.identifiers import require_exact_nonneg_int, require_stable_id

LINEAGE_STORE_SCHEMA: Final[str] = "lineage-store-index-v2"
LINEAGE_INDEX_PAGE_SCHEMA: Final[str] = "lineage-index-page-v2"
LINEAGE_STORE_ROOT_PATH: Final[str] = "store/root.json"
LINEAGE_INDEX_MAX_ENTRIES: Final[int] = 256
LINEAGE_INDEX_MAX_BYTES: Final[int] = LINEAGE_RECORD_MAX_BYTES
LINEAGE_STORE_ROOT_MAX_BYTES: Final[int] = 256 * 1024

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_OBJECT_PATH = re.compile(r"^objects/sha256/[0-9a-f]{2}/[0-9a-f]{64}$")
_MAX_JSON_DEPTH: Final[int] = 32

__all__ = [
    "LINEAGE_INDEX_MAX_BYTES",
    "LINEAGE_INDEX_MAX_ENTRIES",
    "LINEAGE_INDEX_PAGE_SCHEMA",
    "LINEAGE_STORE_ROOT_MAX_BYTES",
    "LINEAGE_STORE_ROOT_PATH",
    "LINEAGE_STORE_SCHEMA",
    "LineageIndexEntry",
    "LineageIndexPage",
    "LineageRootRef",
    "LineageStoreRootV2",
    "build_index_root",
    "compute_store_publication_id",
    "decode_lineage_index_page",
    "decode_store_root",
    "encode_lineage_index_page",
    "encode_store_root",
    "lineage_object_path",
]


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def _digest(value: str) -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise LineageError("lineage_snapshot_corrupt")
    return value


def lineage_object_path(digest: str) -> str:
    _digest(digest)
    return f"objects/sha256/{digest[:2]}/{digest}"


def _object_path(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or value.startswith(("/", "\\"))
        or "\\" in value
        or any(part in ("", ".", "..") for part in value.split("/"))
    ):
        raise LineageError("lineage_snapshot_corrupt")
    return value


def _text_depth_ok(text: str) -> bool:
    depth = 0
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > _MAX_JSON_DEPTH:
                return False
        elif character in "]}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _reject_constant(value: str) -> object:
    raise ValueError("nonfinite")


def _pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _decode(payload: bytes, *, max_bytes: int) -> object:
    if len(payload) > max_bytes:
        raise LineageError("lineage_record_oversize")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LineageError("lineage_snapshot_corrupt") from exc
    if not _text_depth_ok(text):
        raise LineageError("lineage_snapshot_corrupt")
    try:
        return json.loads(
            text,
            object_pairs_hook=_pairs_hook,
            parse_constant=_reject_constant,
        )
    except ValueError as exc:
        raise LineageError("lineage_snapshot_corrupt") from exc


def _require_keys(value: Mapping[str, object], keys: set[str]) -> None:
    if set(value) != keys:
        raise LineageError("lineage_snapshot_corrupt")


@dataclass(frozen=True, slots=True)
class LineageIndexEntry:
    """One authenticated child reference with an exact ordered key range."""

    first_key: str
    last_key: str
    digest: str
    path: str
    row_count: int
    byte_count: int
    is_index: bool

    def __post_init__(self) -> None:
        require_stable_id("index_entry.first_key", self.first_key)
        require_stable_id("index_entry.last_key", self.last_key)
        if self.last_key < self.first_key:
            raise LineageError("lineage_snapshot_corrupt")
        _digest(self.digest)
        _object_path(self.path)
        object.__setattr__(
            self, "row_count", require_exact_nonneg_int("row_count", self.row_count)
        )
        object.__setattr__(
            self, "byte_count", require_exact_nonneg_int("byte_count", self.byte_count)
        )
        if type(self.is_index) is not bool:
            raise LineageError("lineage_snapshot_corrupt")

    def payload(self) -> dict[str, object]:
        return {
            "byte_count": self.byte_count,
            "digest": self.digest,
            "first_key": self.first_key,
            "is_index": self.is_index,
            "last_key": self.last_key,
            "path": self.path,
            "row_count": self.row_count,
        }

    @classmethod
    def from_payload(cls, value: object) -> LineageIndexEntry:
        if type(value) is not dict:
            raise LineageError("lineage_snapshot_corrupt")
        _require_keys(
            value,
            {
                "byte_count",
                "digest",
                "first_key",
                "is_index",
                "last_key",
                "path",
                "row_count",
            },
        )
        return cls(
            first_key=str(value["first_key"]),
            last_key=str(value["last_key"]),
            digest=str(value["digest"]),
            path=str(value["path"]),
            row_count=require_exact_nonneg_int("row_count", value["row_count"]),
            byte_count=require_exact_nonneg_int("byte_count", value["byte_count"]),
            is_index=bool(value["is_index"]),
        )


@dataclass(frozen=True, slots=True)
class LineageIndexPage:
    """One bounded index page; entries point to data or deeper index pages."""

    kind: str
    level: int
    entries: tuple[LineageIndexEntry, ...]
    schema_version: str = LINEAGE_INDEX_PAGE_SCHEMA

    def __post_init__(self) -> None:
        require_stable_id("index_page.kind", self.kind)
        object.__setattr__(
            self, "level", require_exact_nonneg_int("level", self.level)
        )
        if self.level < 1:
            raise LineageError("lineage_snapshot_corrupt")
        entries = tuple(self.entries)
        if not entries:
            raise LineageError("lineage_snapshot_corrupt")
        if len(entries) > LINEAGE_INDEX_MAX_ENTRIES:
            raise LineageError("lineage_record_oversize")
        for entry in entries:
            if type(entry) is not LineageIndexEntry:
                raise LineageError("lineage_snapshot_corrupt")
        object.__setattr__(self, "entries", entries)
        if self.schema_version not in {
            LINEAGE_INDEX_PAGE_SCHEMA,
            "civilization-index-page-v2",
        }:
            raise LineageError("unsupported_lineage_schema")

    def payload(self) -> dict[str, object]:
        return {
            "entries": [entry.payload() for entry in self.entries],
            "kind": self.kind,
            "level": self.level,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_payload(cls, value: object) -> LineageIndexPage:
        if type(value) is not dict:
            raise LineageError("lineage_snapshot_corrupt")
        _require_keys(value, {"entries", "kind", "level", "schema_version"})
        entries = value["entries"]
        if not isinstance(entries, list):
            raise LineageError("lineage_snapshot_corrupt")
        return cls(
            kind=str(value["kind"]),
            level=require_exact_nonneg_int("level", value["level"]),
            entries=tuple(LineageIndexEntry.from_payload(item) for item in entries),
            schema_version=str(value["schema_version"]),
        )


@dataclass(frozen=True, slots=True)
class LineageRootRef:
    """Bounded reference to one index tree; never a flat descendant list."""

    digest: str | None
    path: str | None
    row_count: int
    byte_count: int
    first_key: str | None
    last_key: str | None
    levels: int

    def __post_init__(self) -> None:
        if (self.digest is None) != (self.path is None):
            raise LineageError("lineage_snapshot_corrupt")
        if self.digest is not None:
            _digest(self.digest)
            _object_path(self.path)
        if (self.first_key is None) != (self.last_key is None):
            raise LineageError("lineage_snapshot_corrupt")
        if self.first_key is not None:
            require_stable_id("root_ref.first_key", self.first_key)
            require_stable_id("root_ref.last_key", self.last_key)
            if (
                self.first_key is not None
                and self.last_key is not None
                and self.last_key < self.first_key
            ):
                raise LineageError("lineage_snapshot_corrupt")
        object.__setattr__(
            self, "row_count", require_exact_nonneg_int("row_count", self.row_count)
        )
        object.__setattr__(
            self, "byte_count", require_exact_nonneg_int("byte_count", self.byte_count)
        )
        object.__setattr__(
            self, "levels", require_exact_nonneg_int("levels", self.levels)
        )
        if self.digest is None and (self.row_count or self.byte_count or self.levels):
            raise LineageError("lineage_snapshot_corrupt")

    def payload(self) -> dict[str, object]:
        return {
            "byte_count": self.byte_count,
            "digest": self.digest,
            "first_key": self.first_key,
            "last_key": self.last_key,
            "levels": self.levels,
            "path": self.path,
            "row_count": self.row_count,
        }

    @classmethod
    def from_payload(cls, value: object) -> LineageRootRef:
        if type(value) is not dict:
            raise LineageError("lineage_snapshot_corrupt")
        _require_keys(
            value,
            {
                "byte_count",
                "digest",
                "first_key",
                "last_key",
                "levels",
                "path",
                "row_count",
            },
        )
        digest = value["digest"]
        path = value["path"]
        return cls(
            digest=None if digest is None else str(digest),
            path=None if path is None else str(path),
            row_count=require_exact_nonneg_int("row_count", value["row_count"]),
            byte_count=require_exact_nonneg_int("byte_count", value["byte_count"]),
            first_key=None if value["first_key"] is None else str(value["first_key"]),
            last_key=None if value["last_key"] is None else str(value["last_key"]),
            levels=require_exact_nonneg_int("levels", value["levels"]),
        )


@dataclass(frozen=True, slots=True)
class LineageStoreRootV2:
    """Fixed-size physical root for one v2 lineage publication."""

    run_id: RunId
    family: LineageFamily
    evidence_class: LineageEvidenceClass
    owner_id: str | None
    boundary_tick: int
    publication_id: str
    content_digest: str
    source_revision: str
    policy_version: str
    coverage: LineageCoverage
    node_count: int
    edge_count: int
    catalog: LineageRootRef
    adjacency: LineageRootRef
    identity: LineageRootRef
    integrity: LineageRootRef
    object_count: int
    object_bytes: int
    schema_version: str = LINEAGE_STORE_SCHEMA

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise LineageError("lineage_snapshot_corrupt")
        if type(self.family) is not LineageFamily:
            raise LineageError("lineage_snapshot_corrupt")
        if type(self.evidence_class) is not LineageEvidenceClass:
            raise LineageError("lineage_snapshot_corrupt")
        if self.evidence_class is LineageEvidenceClass.SUBJECTIVE:
            if self.owner_id is None:
                raise LineageError("lineage_scope_mismatch")
        elif self.owner_id is not None:
            raise LineageError("lineage_scope_mismatch")
        object.__setattr__(
            self,
            "boundary_tick",
            require_exact_nonneg_int("boundary_tick", self.boundary_tick),
        )
        object.__setattr__(self, "publication_id", _digest(self.publication_id))
        object.__setattr__(self, "content_digest", _digest(self.content_digest))
        object.__setattr__(
            self,
            "source_revision",
            require_stable_id("source_revision", self.source_revision),
        )
        object.__setattr__(
            self,
            "policy_version",
            require_stable_id("policy_version", self.policy_version),
        )
        if type(self.coverage) is not LineageCoverage:
            raise LineageError("lineage_snapshot_corrupt")
        for name in ("node_count", "edge_count", "object_count", "object_bytes"):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(name, getattr(self, name)),
            )
        for name in ("catalog", "adjacency", "identity", "integrity"):
            if type(getattr(self, name)) is not LineageRootRef:
                raise LineageError("lineage_snapshot_corrupt")
        if self.schema_version != LINEAGE_STORE_SCHEMA:
            raise LineageError("unsupported_lineage_schema")

    def payload(self, *, include_id: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "adjacency": self.adjacency.payload(),
            "boundary_tick": self.boundary_tick,
            "catalog": self.catalog.payload(),
            "content_digest": self.content_digest,
            "coverage": _coverage_payload(self.coverage),
            "edge_count": self.edge_count,
            "evidence_class": self.evidence_class.value,
            "family": self.family.value,
            "identity": self.identity.payload(),
            "integrity": self.integrity.payload(),
            "node_count": self.node_count,
            "object_bytes": self.object_bytes,
            "object_count": self.object_count,
            "owner_id": self.owner_id,
            "policy_version": self.policy_version,
            "run_id": self.run_id.value,
            "schema_version": self.schema_version,
            "source_revision": self.source_revision,
        }
        if include_id:
            document["publication_id"] = self.publication_id
        return document


def compute_store_publication_id(root: LineageStoreRootV2) -> str:
    return hashlib.sha256(_canonical(root.payload(include_id=False))).hexdigest()


def encode_store_root(root: LineageStoreRootV2) -> bytes:
    if compute_store_publication_id(root) != root.publication_id:
        raise LineageError("lineage_digest_mismatch")
    payload = _canonical(root.payload())
    if len(payload) > LINEAGE_STORE_ROOT_MAX_BYTES:
        raise LineageError("lineage_record_oversize")
    return payload


def decode_store_root(payload: bytes) -> LineageStoreRootV2:
    value = _decode(payload, max_bytes=LINEAGE_STORE_ROOT_MAX_BYTES)
    if type(value) is not dict:
        raise LineageError("lineage_snapshot_corrupt")
    _require_keys(
        value,
        {
            "adjacency",
            "boundary_tick",
            "catalog",
            "content_digest",
            "coverage",
            "edge_count",
            "evidence_class",
            "family",
            "identity",
            "integrity",
            "node_count",
            "object_bytes",
            "object_count",
            "owner_id",
            "policy_version",
            "publication_id",
            "run_id",
            "schema_version",
            "source_revision",
        },
    )
    root = LineageStoreRootV2(
        run_id=RunId(str(value["run_id"])),
        family=LineageFamily(str(value["family"])),
        evidence_class=LineageEvidenceClass(str(value["evidence_class"])),
        owner_id=None if value["owner_id"] is None else str(value["owner_id"]),
        boundary_tick=require_exact_nonneg_int(
            "boundary_tick", value["boundary_tick"]
        ),
        publication_id=str(value["publication_id"]),
        content_digest=str(value["content_digest"]),
        source_revision=str(value["source_revision"]),
        policy_version=str(value["policy_version"]),
        coverage=_coverage_decode(value["coverage"]),
        node_count=require_exact_nonneg_int("node_count", value["node_count"]),
        edge_count=require_exact_nonneg_int("edge_count", value["edge_count"]),
        catalog=LineageRootRef.from_payload(value["catalog"]),
        adjacency=LineageRootRef.from_payload(value["adjacency"]),
        identity=LineageRootRef.from_payload(value["identity"]),
        integrity=LineageRootRef.from_payload(value["integrity"]),
        object_count=require_exact_nonneg_int(
            "object_count", value["object_count"]
        ),
        object_bytes=require_exact_nonneg_int(
            "object_bytes", value["object_bytes"]
        ),
        schema_version=str(value["schema_version"]),
    )
    if compute_store_publication_id(root) != root.publication_id:
        raise LineageError("lineage_digest_mismatch")
    return root


def _coverage_payload(coverage: LineageCoverage) -> dict[str, object]:
    return {
        "capture_end_tick": coverage.capture_end_tick,
        "capture_start_tick": coverage.capture_start_tick,
        "missing_prefix_tick": coverage.missing_prefix_tick,
        "policy_version": coverage.policy_version,
        "pruned_count": coverage.pruned_count,
        "reason_codes": list(coverage.reason_codes),
        "state": coverage.state.value,
        "unresolved_count": coverage.unresolved_count,
    }


def _coverage_decode(value: object) -> LineageCoverage:
    if type(value) is not dict:
        raise LineageError("lineage_snapshot_corrupt")
    _require_keys(
        value,
        {
            "capture_end_tick",
            "capture_start_tick",
            "missing_prefix_tick",
            "policy_version",
            "pruned_count",
            "reason_codes",
            "state",
            "unresolved_count",
        },
    )
    reasons = value["reason_codes"]
    if not isinstance(reasons, list):
        raise LineageError("lineage_snapshot_corrupt")
    return LineageCoverage(
        state=LineageCoverageState(str(value["state"])),
        reason_codes=tuple(str(item) for item in reasons),
        capture_start_tick=_optional_tick(value["capture_start_tick"]),
        capture_end_tick=_optional_tick(value["capture_end_tick"]),
        missing_prefix_tick=_optional_tick(value["missing_prefix_tick"]),
        pruned_count=require_exact_nonneg_int("pruned_count", value["pruned_count"]),
        unresolved_count=require_exact_nonneg_int(
            "unresolved_count", value["unresolved_count"]
        ),
        policy_version=(
            None if value["policy_version"] is None else str(value["policy_version"])
        ),
    )


def _optional_tick(value: object) -> int | None:
    if value is None:
        return None
    return require_exact_nonneg_int("tick", value)


def encode_lineage_index_page(page: LineageIndexPage) -> bytes:
    if type(page) is not LineageIndexPage:
        raise LineageError("lineage_snapshot_corrupt")
    payload = _canonical(page.payload())
    if len(payload) > LINEAGE_INDEX_MAX_BYTES:
        raise LineageError("lineage_record_oversize")
    return payload


def decode_lineage_index_page(
    payload: bytes, *, schema: str = LINEAGE_INDEX_PAGE_SCHEMA
) -> LineageIndexPage:
    value = _decode(payload, max_bytes=LINEAGE_INDEX_MAX_BYTES)
    page = LineageIndexPage.from_payload(value)
    if page.schema_version != schema:
        raise LineageError("unsupported_lineage_schema")
    return page


def build_index_root(
    kind: str,
    entries: Sequence[LineageIndexEntry],
    *,
    page_schema: str = LINEAGE_INDEX_PAGE_SCHEMA,
    max_bytes: int = LINEAGE_INDEX_MAX_BYTES,
) -> tuple[LineageRootRef, dict[str, bytes]]:
    """Build a bottom-up bounded index tree over already-addressed entries.

    Returned objects are keyed by SHA-256 digest and use the run-level
    ``objects/sha256/..`` path convention. A single oversized entry fails
    closed rather than being split or truncated.
    """
    require_stable_id("index.kind", kind)
    rows = list(entries)
    objects: dict[str, bytes] = {}
    if not rows:
        return LineageRootRef(None, None, 0, 0, None, None, 0), objects
    if any(type(entry) is not LineageIndexEntry for entry in rows):
        raise LineageError("lineage_snapshot_corrupt")
    first_key = rows[0].first_key
    last_key = rows[-1].last_key
    total_rows = sum(entry.row_count for entry in rows)
    total_bytes = sum(entry.byte_count for entry in rows)
    level = 0
    current = rows
    while True:
        level += 1
        page_candidates = _group_entries(
            current,
            kind=kind,
            level=level,
            page_schema=page_schema,
            max_bytes=max_bytes,
        )
        if len(page_candidates) == 1 and level == 1:
            page = page_candidates[0]
            content = _canonical(page.payload())
            if len(content) <= max_bytes:
                digest = hashlib.sha256(content).hexdigest()
                objects[digest] = content
                return (
                    LineageRootRef(
                        digest=digest,
                        path=lineage_object_path(digest),
                        row_count=total_rows,
                        byte_count=total_bytes,
                        first_key=first_key,
                        last_key=last_key,
                        levels=level,
                    ),
                    objects,
                )
        next_entries: list[LineageIndexEntry] = []
        for page in page_candidates:
            content = _canonical(page.payload())
            if len(content) > max_bytes:
                raise LineageError("lineage_record_oversize")
            digest = hashlib.sha256(content).hexdigest()
            objects[digest] = content
            next_entries.append(
                LineageIndexEntry(
                    first_key=page.entries[0].first_key,
                    last_key=page.entries[-1].last_key,
                    digest=digest,
                    path=lineage_object_path(digest),
                    row_count=sum(entry.row_count for entry in page.entries),
                    byte_count=sum(entry.byte_count for entry in page.entries),
                    is_index=True,
                )
            )
        if len(page_candidates) == 1:
            content = _canonical(page_candidates[0].payload())
            digest = hashlib.sha256(content).hexdigest()
            objects[digest] = content
            return (
                LineageRootRef(
                    digest=digest,
                    path=lineage_object_path(digest),
                    row_count=total_rows,
                    byte_count=total_bytes,
                    first_key=first_key,
                    last_key=last_key,
                    levels=level,
                ),
                objects,
            )
        current = next_entries


def _group_entries(
    entries: Sequence[LineageIndexEntry],
    *,
    kind: str,
    level: int,
    page_schema: str,
    max_bytes: int,
) -> list[LineageIndexPage]:
    pages: list[LineageIndexPage] = []
    chunk: list[LineageIndexEntry] = []
    for entry in entries:
        if len(chunk) >= LINEAGE_INDEX_MAX_ENTRIES:
            pages.append(
                LineageIndexPage(
                    kind=kind,
                    level=level,
                    entries=tuple(chunk),
                    schema_version=page_schema,
                )
            )
            chunk = []
        candidate = (*chunk, entry)
        encoded = _canonical(
            LineageIndexPage(
                kind=kind,
                level=level,
                entries=tuple(candidate),
                schema_version=page_schema,
            ).payload()
        )
        if chunk and len(encoded) > max_bytes:
            pages.append(
                LineageIndexPage(
                    kind=kind,
                    level=level,
                    entries=tuple(chunk),
                    schema_version=page_schema,
                )
            )
            # Start the next page empty; the shared append below adds this entry
            # exactly once. Pre-seeding the chunk duplicated the first entry of
            # every byte-split page and broke strictly increasing key ranges.
            chunk = []
            encoded = _canonical(
                LineageIndexPage(
                    kind=kind, level=level, entries=(entry,)
                ).payload()
            )
        if len(encoded) > max_bytes:
            raise LineageError("lineage_record_oversize")
        chunk.append(entry)
    if chunk:
        pages.append(LineageIndexPage(
                    kind=kind,
                    level=level,
                    entries=tuple(chunk),
                    schema_version=page_schema,
                ))
    return pages
