"""Strict canonical codec for immutable lineage-snapshot-v1 artifacts.

Every file is duplicate-key aware, depth bounded, exact-key and finite-number
checked before typed construction. Artifact digests are integrity checks, not
authenticity or truth.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Final

from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageEvidenceRef,
    LineageFamily,
    LineageNativeKind,
    LineageNodeRef,
    require_lineage_key,
)
from simulation.lineage_models import (
    LINEAGE_SNAPSHOT_SCHEMA_VERSION,
    LineageCoverage,
    LineageCoverageState,
    LineageDirection,
    LineageEdge,
    LineageError,
    LineageNode,
    LineageNodeState,
    LineageScope,
    LineageSnapshotRef,
    MentorshipLineageRecord,
    require_lineage_cursor,
)
from simulation.lineage_ports import (
    CAPTURE_MAX_EDGES,
    CAPTURE_MAX_NODES,
    LineageBoundaryFrame,
    LineagePublication,
)
from simulation.models import RunId
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "LINEAGE_ADJACENCY_PAGE_MAX_EDGES",
    "LINEAGE_CONTROL_SCHEMA_VERSION",
    "LINEAGE_DESCRIPTOR_MAX_BYTES",
    "LINEAGE_MANIFEST_MAX_BYTES",
    "LINEAGE_NODE_PAGE_MAX_NODES",
    "LINEAGE_RECORD_MAX_BYTES",
    "LineageAdjacencyPage",
    "LineageControlRecord",
    "LineageNodePage",
    "LineageSnapshotManifest",
    "compute_publication_id",
    "decode_lineage_adjacency_page",
    "decode_lineage_control_record",
    "decode_lineage_manifest",
    "decode_lineage_node_descriptor",
    "decode_lineage_node_page",
    "decode_lineage_publication",
    "encode_lineage_adjacency_page",
    "encode_lineage_control_record",
    "encode_lineage_manifest",
    "encode_lineage_node_descriptor",
    "encode_lineage_node_page",
    "encode_lineage_publication",
]

LINEAGE_MANIFEST_MAX_BYTES: Final[int] = 256 * 1024
LINEAGE_RECORD_MAX_BYTES: Final[int] = 256 * 1024
LINEAGE_DESCRIPTOR_MAX_BYTES: Final[int] = 8 * 1024
LINEAGE_NODE_PAGE_MAX_NODES: Final[int] = 256
LINEAGE_ADJACENCY_PAGE_MAX_EDGES: Final[int] = 256
LINEAGE_CONTROL_SCHEMA_VERSION: Final[str] = "lineage-control-v1"
_MAX_JSON_DEPTH: Final[int] = 32
_DIGEST_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_PAGE_PATH_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"^nodes/([0-9a-f]{64}|[0-9]{4})\.json$"),
    re.compile(
        r"^adjacency/[0-9a-f]{64}-((ancestors|descendants)-)?[0-9]{4}\.json$"
    ),
    re.compile(r"^catalog/nodes-[0-9]{4}\.json$"),
    re.compile(r"^lookup/[0-9a-f]{2}\.json$"),
    re.compile(r"^integrity/[0-9a-f]{2}\.json$"),
)


def _valid_page_path(path: object) -> bool:
    return isinstance(path, str) and any(
        pattern.match(path) for pattern in _PAGE_PATH_PATTERNS
    )


def _text_depth_ok(text: str) -> bool:
    """Reject excessive nesting before allocating the parsed object graph."""
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


class _DuplicateKey(ValueError):
    pass


class _NonFinite(ValueError):
    pass


def _reject_constant(value: str) -> object:
    raise _NonFinite(value)


def _pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey("duplicate_json_key")
        result[key] = value
    return result


def _depth_ok(value: object, *, depth: int = 0) -> bool:
    if depth > _MAX_JSON_DEPTH:
        return False
    if isinstance(value, Mapping):
        return all(
            _depth_ok(key, depth=depth + 1) and _depth_ok(item, depth=depth + 1)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return all(_depth_ok(item, depth=depth + 1) for item in value)
    return True


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


def _decode_json(payload: bytes, *, max_bytes: int) -> object:
    if type(payload) is not bytes:
        raise ValueError("lineage_record_invalid")
    if len(payload) > max_bytes:
        raise LineageError("lineage_record_oversize")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("lineage_record_invalid") from exc
    if not _text_depth_ok(text):
        raise ValueError("lineage_record_invalid")
    try:
        document = json.loads(
            text,
            object_pairs_hook=_pairs_hook,
            parse_constant=_reject_constant,
        )
    except _DuplicateKey as exc:
        raise LineageError("lineage_identity_conflict") from exc
    except (_NonFinite, ValueError) as exc:
        raise ValueError("lineage_record_invalid") from exc
    if not isinstance(document, dict):
        raise ValueError("lineage_record_invalid")
    if not _depth_ok(document):
        raise ValueError("lineage_record_invalid")
    return document


def _exact(document: object, expected: frozenset[str]) -> Mapping[str, object]:
    if not isinstance(document, dict) or set(document) != expected:
        raise ValueError("lineage_record_invalid")
    return document


def _digest(value: object) -> str:
    return require_lineage_key("digest", value)


def _nonneg(value: object) -> int:
    return require_exact_nonneg_int("value", value)


def _optional_id(value: object) -> str | None:
    if value is None:
        return None
    return require_stable_id("value", value)


def _optional_tick(value: object) -> int | None:
    if value is None:
        return None
    return require_exact_nonneg_int("tick", value)


def _optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    if type(value) is not bool:
        raise ValueError("lineage_record_invalid")
    return value


def _optional_cursor(value: object) -> str | None:
    if value is None:
        return None
    return require_lineage_cursor(value)


def _finite(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("lineage_record_invalid")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("lineage_record_invalid")
    return number


def _counts(value: object) -> tuple[tuple[str, int], ...]:
    if not isinstance(value, list):
        raise ValueError("lineage_record_invalid")
    result: list[tuple[str, int]] = []
    for item in value:
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError("lineage_record_invalid")
        result.append(
            (
                require_stable_id("count.key", item[0]),
                require_exact_nonneg_int("count.value", item[1]),
            )
        )
    return tuple(result)


def _counts_payload(counts: tuple[tuple[str, int], ...]) -> list[list[object]]:
    return [[key, value] for key, value in counts]


def _evidence_payload(evidence: LineageEvidenceRef) -> dict[str, object]:
    return {
        "evidence_class": evidence.evidence_class.value,
        "native_id": evidence.native_id,
        "native_kind": evidence.native_kind.value,
        "observed_tick": evidence.observed_tick,
        "owner_id": evidence.owner_id,
    }


def _evidence_decode(value: object) -> LineageEvidenceRef:
    document = _exact(
        value,
        frozenset(
            {
                "evidence_class",
                "native_id",
                "native_kind",
                "observed_tick",
                "owner_id",
            }
        ),
    )
    return LineageEvidenceRef(
        evidence_class=LineageEvidenceClass(str(document["evidence_class"])),
        native_kind=LineageNativeKind(str(document["native_kind"])),
        native_id=str(document["native_id"]),
        owner_id=_optional_id(document["owner_id"]),
        observed_tick=_optional_tick(document["observed_tick"]),
    )


def _mentorship_payload(record: MentorshipLineageRecord) -> dict[str, object]:
    return {
        "acquisition_tick": record.acquisition_tick,
        "attempt_count": record.attempt_count,
        "confidence_band": record.confidence_band,
        "content_key": record.content_key,
        "content_kind": record.content_kind,
        "evidence_refs": [_evidence_payload(item) for item in record.evidence_refs],
        "hop": record.hop,
        "learner_id": record.learner_id,
        "learning_evidence_count": record.learning_evidence_count,
        "lineage_id": record.lineage_id,
        "mutated": record.mutated,
        "native_status": record.native_status,
        "observed_boundary": record.observed_boundary,
        "owner_id": record.owner_id,
        "parent_ids": list(record.parent_ids),
        "policy_version": record.policy_version,
        "root_id": record.root_id,
        "source_observed_boundary": record.source_observed_boundary,
        "source_revision": record.source_revision,
        "teacher_id": record.teacher_id,
        "update_tick": record.update_tick,
    }


def _mentorship_decode(value: object) -> MentorshipLineageRecord:
    document = _exact(
        value,
        frozenset(
            {
                "acquisition_tick",
                "attempt_count",
                "confidence_band",
                "content_key",
                "content_kind",
                "evidence_refs",
                "hop",
                "learner_id",
                "learning_evidence_count",
                "lineage_id",
                "mutated",
                "native_status",
                "observed_boundary",
                "owner_id",
                "parent_ids",
                "policy_version",
                "root_id",
                "source_observed_boundary",
                "source_revision",
                "teacher_id",
                "update_tick",
            }
        ),
    )
    refs = document["evidence_refs"]
    parents = document["parent_ids"]
    mutated = document["mutated"]
    if not isinstance(refs, list) or not isinstance(parents, list):
        raise ValueError("lineage_record_invalid")
    if type(mutated) is not bool:
        raise ValueError("lineage_record_invalid")
    return MentorshipLineageRecord(
        owner_id=require_stable_id("owner_id", document["owner_id"]),
        teacher_id=require_stable_id("teacher_id", document["teacher_id"]),
        learner_id=require_stable_id("learner_id", document["learner_id"]),
        lineage_id=require_stable_id("lineage_id", document["lineage_id"]),
        root_id=require_stable_id("root_id", document["root_id"]),
        parent_ids=tuple(
            require_stable_id("parent_id", item) for item in parents
        ),
        content_kind=require_stable_id("content_kind", document["content_kind"]),
        content_key=require_stable_id("content_key", document["content_key"]),
        hop=require_exact_nonneg_int("hop", document["hop"]),
        acquisition_tick=require_exact_nonneg_int(
            "acquisition_tick", document["acquisition_tick"]
        ),
        update_tick=require_exact_nonneg_int("update_tick", document["update_tick"]),
        attempt_count=require_exact_nonneg_int(
            "attempt_count", document["attempt_count"]
        ),
        learning_evidence_count=require_exact_nonneg_int(
            "learning_evidence_count", document["learning_evidence_count"]
        ),
        confidence_band=_optional_id(document["confidence_band"]),
        mutated=mutated,
        evidence_refs=tuple(_evidence_decode(item) for item in refs),
        policy_version=require_stable_id(
            "policy_version", document["policy_version"]
        ),
        observed_boundary=require_exact_nonneg_int(
            "observed_boundary", document["observed_boundary"]
        ),
        source_observed_boundary=require_exact_nonneg_int(
            "source_observed_boundary", document["source_observed_boundary"]
        ),
        native_status=_optional_id(document["native_status"]),
        source_revision=_optional_id(document["source_revision"]),
    )


def _ref_payload(ref: LineageNodeRef) -> dict[str, object]:
    return {
        "evidence_class": ref.evidence_class.value,
        "family": ref.family.value,
        "identity_owner": ref.identity_owner,
        "native_id": ref.native_id,
        "native_kind": ref.native_kind.value,
        "run_id": ref.run_id.value,
    }


def _ref_decode(value: object) -> LineageNodeRef:
    document = _exact(
        value,
        frozenset(
            {
                "evidence_class",
                "family",
                "identity_owner",
                "native_id",
                "native_kind",
                "run_id",
            }
        ),
    )
    return LineageNodeRef(
        run_id=RunId(str(document["run_id"])),
        family=LineageFamily(str(document["family"])),
        evidence_class=LineageEvidenceClass(str(document["evidence_class"])),
        native_kind=LineageNativeKind(str(document["native_kind"])),
        native_id=str(document["native_id"]),
        identity_owner=_optional_id(document["identity_owner"]),
    )


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
    document = _exact(
        value,
        frozenset(
            {
                "capture_end_tick",
                "capture_start_tick",
                "missing_prefix_tick",
                "policy_version",
                "pruned_count",
                "reason_codes",
                "state",
                "unresolved_count",
            }
        ),
    )
    reasons = document["reason_codes"]
    if not isinstance(reasons, list):
        raise ValueError("lineage_record_invalid")
    return LineageCoverage(
        state=LineageCoverageState(str(document["state"])),
        reason_codes=tuple(str(item) for item in reasons),
        capture_start_tick=_optional_tick(document["capture_start_tick"]),
        capture_end_tick=_optional_tick(document["capture_end_tick"]),
        missing_prefix_tick=_optional_tick(document["missing_prefix_tick"]),
        pruned_count=_nonneg(document["pruned_count"]),
        unresolved_count=_nonneg(document["unresolved_count"]),
        policy_version=_optional_id(document["policy_version"]),
    )


@dataclass(frozen=True, slots=True)
class LineageSnapshotManifest:
    """One immutable publication manifest (content identity, not authority)."""

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
    page_count: int
    page_digests: tuple[tuple[str, str], ...]
    schema_version: str = LINEAGE_SNAPSHOT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise ValueError("manifest run_id must be RunId")
        if type(self.family) is not LineageFamily:
            raise ValueError("manifest family must be LineageFamily")
        if type(self.evidence_class) is not LineageEvidenceClass:
            raise ValueError("manifest evidence_class must be LineageEvidenceClass")
        owner = _optional_id(self.owner_id)
        if self.evidence_class is LineageEvidenceClass.SUBJECTIVE and owner is None:
            raise LineageError("lineage_scope_mismatch")
        if (
            self.evidence_class is not LineageEvidenceClass.SUBJECTIVE
            and owner is not None
        ):
            raise LineageError("lineage_scope_mismatch")
        object.__setattr__(self, "owner_id", owner)
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
            raise ValueError("manifest coverage must be LineageCoverage")
        for name in ("node_count", "edge_count", "page_count"):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(f"manifest {name}", getattr(self, name)),
            )
        pages = tuple(self.page_digests)
        seen: set[str] = set()
        for item in pages:
            if not isinstance(item, tuple) or len(item) != 2:
                raise ValueError("manifest page_digests must be pairs")
            path = require_stable_id("page_path", item[0])
            if not _valid_page_path(path):
                raise ValueError("path-shaped lineage page id")
            if path in seen:
                raise LineageError("lineage_identity_conflict")
            seen.add(path)
            _digest(item[1])
        object.__setattr__(self, "page_digests", pages)
        if self.schema_version != LINEAGE_SNAPSHOT_SCHEMA_VERSION:
            raise LineageError("unsupported_lineage_schema")


def _manifest_payload(
    manifest: LineageSnapshotManifest, *, include_id: bool
) -> dict[str, object]:
    payload: dict[str, object] = {
        "boundary_tick": manifest.boundary_tick,
        "content_digest": manifest.content_digest,
        "coverage": _coverage_payload(manifest.coverage),
        "edge_count": manifest.edge_count,
        "evidence_class": manifest.evidence_class.value,
        "family": manifest.family.value,
        "node_count": manifest.node_count,
        "owner_id": manifest.owner_id,
        "page_count": manifest.page_count,
        "page_digests": [[path, digest] for path, digest in manifest.page_digests],
        "policy_version": manifest.policy_version,
        "run_id": manifest.run_id.value,
        "schema_version": manifest.schema_version,
        "source_revision": manifest.source_revision,
    }
    if include_id:
        payload["publication_id"] = manifest.publication_id
    return payload


def compute_publication_id(manifest: LineageSnapshotManifest) -> str:
    encoded = _canonical(_manifest_payload(manifest, include_id=False))
    return hashlib.sha256(encoded).hexdigest()


def encode_lineage_manifest(manifest: LineageSnapshotManifest) -> bytes:
    if type(manifest) is not LineageSnapshotManifest:
        raise ValueError("manifest must be LineageSnapshotManifest")
    if compute_publication_id(manifest) != manifest.publication_id:
        raise LineageError("lineage_digest_mismatch")
    return _canonical(_manifest_payload(manifest, include_id=True))


def decode_lineage_manifest(payload: bytes) -> LineageSnapshotManifest:
    document = _exact(
        _decode_json(payload, max_bytes=LINEAGE_MANIFEST_MAX_BYTES),
        frozenset(
            {
                "boundary_tick",
                "content_digest",
                "coverage",
                "edge_count",
                "evidence_class",
                "family",
                "node_count",
                "owner_id",
                "page_count",
                "page_digests",
                "policy_version",
                "publication_id",
                "run_id",
                "schema_version",
                "source_revision",
            }
        ),
    )
    pages = document["page_digests"]
    if not isinstance(pages, list):
        raise ValueError("lineage_record_invalid")
    page_pairs: list[tuple[str, str]] = []
    for item in pages:
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError("lineage_record_invalid")
        if not isinstance(item[0], str) or not isinstance(item[1], str):
            raise ValueError("lineage_record_invalid")
        page_pairs.append((item[0], item[1]))
    if _nonneg(document["page_count"]) != len(page_pairs):
        raise ValueError("lineage_record_invalid")
    manifest = LineageSnapshotManifest(
        run_id=RunId(str(document["run_id"])),
        family=LineageFamily(str(document["family"])),
        evidence_class=LineageEvidenceClass(str(document["evidence_class"])),
        owner_id=_optional_id(document["owner_id"]),
        boundary_tick=_nonneg(document["boundary_tick"]),
        publication_id=_digest(document["publication_id"]),
        content_digest=_digest(document["content_digest"]),
        source_revision=str(document["source_revision"]),
        policy_version=str(document["policy_version"]),
        coverage=_coverage_decode(document["coverage"]),
        node_count=_nonneg(document["node_count"]),
        edge_count=_nonneg(document["edge_count"]),
        page_count=_nonneg(document["page_count"]),
        page_digests=tuple(page_pairs),
        schema_version=str(document["schema_version"]),
    )
    if compute_publication_id(manifest) != manifest.publication_id:
        raise LineageError("lineage_digest_mismatch")
    return manifest


def encode_lineage_node_descriptor(node: LineageNode) -> bytes:
    if type(node) is not LineageNode:
        raise ValueError("node must be LineageNode")
    document = {
        "confidence_code": node.confidence_code,
        "confidence_value": node.confidence_value,
        "counts": _counts_payload(node.counts),
        "custodian_repository_id": node.custodian_repository_id,
        "evidence_refs": [_evidence_payload(item) for item in node.evidence_refs],
        "living": node.living,
        "mentorship_record": (
            None
            if node.mentorship_record is None
            else _mentorship_payload(node.mentorship_record)
        ),
        "native_revision": node.native_revision,
        "observed_tick": node.observed_tick,
        "ref": _ref_payload(node.ref),
        "source_loss_reason": node.source_loss_reason,
        "source_loss_state": node.source_loss_state,
        "source_observed_boundary": node.source_observed_boundary,
        "state": node.state.value,
        "status_code": node.status_code,
        "unresolved_reason": node.unresolved_reason,
    }
    return _canonical(document)


def decode_lineage_node_descriptor(payload: bytes) -> LineageNode:
    document = _exact(
        _decode_json(payload, max_bytes=LINEAGE_DESCRIPTOR_MAX_BYTES),
        frozenset(
            {
                "confidence_code",
                "confidence_value",
                "counts",
                "custodian_repository_id",
                "evidence_refs",
                "living",
                "mentorship_record",
                "native_revision",
                "observed_tick",
                "ref",
                "source_loss_reason",
                "source_loss_state",
                "source_observed_boundary",
                "state",
                "status_code",
                "unresolved_reason",
            }
        ),
    )
    refs = document["evidence_refs"]
    if not isinstance(refs, list):
        raise ValueError("lineage_record_invalid")
    mentorship = document["mentorship_record"]
    return LineageNode(
        ref=_ref_decode(document["ref"]),
        state=LineageNodeState(str(document["state"])),
        living=_optional_bool(document["living"]),
        mentorship_record=(
            None if mentorship is None else _mentorship_decode(mentorship)
        ),
        observed_tick=_optional_tick(document["observed_tick"]),
        status_code=_optional_id(document["status_code"]),
        confidence_code=_optional_id(document["confidence_code"]),
        confidence_value=_finite(document["confidence_value"]),
        unresolved_reason=_optional_id(document["unresolved_reason"]),
        native_revision=_optional_id(document["native_revision"]),
        evidence_refs=tuple(_evidence_decode(item) for item in refs),
        counts=_counts(document["counts"]),
        source_observed_boundary=_optional_tick(document["source_observed_boundary"]),
        custodian_repository_id=_optional_id(document["custodian_repository_id"]),
        source_loss_state=_optional_id(document["source_loss_state"]),
        source_loss_reason=_optional_id(document["source_loss_reason"]),
    )


@dataclass(frozen=True, slots=True)
class LineageNodePage:
    nodes: tuple[LineageNode, ...]
    next_key: str | None = None

    def __post_init__(self) -> None:
        nodes = tuple(self.nodes)
        for node in nodes:
            if type(node) is not LineageNode:
                raise ValueError("nodes must be LineageNode")
        if len(nodes) > LINEAGE_NODE_PAGE_MAX_NODES:
            raise LineageError("lineage_record_oversize")
        if len({node.key for node in nodes}) != len(nodes):
            raise LineageError("lineage_identity_conflict")
        object.__setattr__(self, "nodes", nodes)
        if self.next_key is not None:
            object.__setattr__(self, "next_key", require_lineage_cursor(self.next_key))


def encode_lineage_node_page(page: LineageNodePage) -> bytes:
    if type(page) is not LineageNodePage:
        raise ValueError("page must be LineageNodePage")
    payload = {
        "next_key": page.next_key,
        "nodes": [
            json.loads(encode_lineage_node_descriptor(node))
            for node in sorted(page.nodes, key=lambda item: item.key)
        ],
    }
    return _canonical(payload)


def decode_lineage_node_page(payload: bytes) -> LineageNodePage:
    document = _exact(
        _decode_json(payload, max_bytes=LINEAGE_RECORD_MAX_BYTES),
        frozenset({"next_key", "nodes"}),
    )
    nodes = document["nodes"]
    if not isinstance(nodes, list) or len(nodes) > LINEAGE_NODE_PAGE_MAX_NODES:
        raise LineageError("lineage_record_oversize")
    decoded = tuple(decode_lineage_node_descriptor(_canonical(item)) for item in nodes)
    return LineageNodePage(
        nodes=decoded, next_key=_optional_cursor(document["next_key"])
    )


def _edge_payload(edge: LineageEdge) -> dict[str, object]:
    return {
        "claim_owner_id": edge.claim_owner_id,
        "confidence_code": edge.confidence_code,
        "confidence_value": edge.confidence_value,
        "counts": _counts_payload(edge.counts),
        "edge_key": edge.edge_key,
        "evidence_refs": [_evidence_payload(item) for item in edge.evidence_refs],
        "last_observed_boundary": edge.last_observed_boundary,
        "native_id": edge.native_id,
        "native_kind": edge.native_kind.value,
        "observed_tick": edge.observed_tick,
        "relation": edge.relation,
        "source_key": edge.source_key,
        "source_presence": edge.source_presence,
        "status_code": edge.status_code,
        "target_key": edge.target_key,
    }


def _edge_decode(value: object) -> LineageEdge:
    document = _exact(
        value,
        frozenset(
            {
                "claim_owner_id",
                "confidence_code",
                "confidence_value",
                "counts",
                "edge_key",
                "evidence_refs",
                "last_observed_boundary",
                "native_id",
                "native_kind",
                "observed_tick",
                "relation",
                "source_key",
                "source_presence",
                "status_code",
                "target_key",
            }
        ),
    )
    refs = document["evidence_refs"]
    if not isinstance(refs, list):
        raise ValueError("lineage_record_invalid")
    return LineageEdge(
        edge_key=str(document["edge_key"]),
        source_key=str(document["source_key"]),
        target_key=str(document["target_key"]),
        relation=str(document["relation"]),
        native_kind=LineageNativeKind(str(document["native_kind"])),
        native_id=str(document["native_id"]),
        claim_owner_id=_optional_id(document["claim_owner_id"]),
        evidence_refs=tuple(_evidence_decode(item) for item in refs),
        observed_tick=_optional_tick(document["observed_tick"]),
        last_observed_boundary=_optional_tick(document["last_observed_boundary"]),
        status_code=_optional_id(document["status_code"]),
        confidence_code=_optional_id(document["confidence_code"]),
        confidence_value=_finite(document["confidence_value"]),
        source_presence=str(document["source_presence"]),
        counts=_counts(document["counts"]),
    )


@dataclass(frozen=True, slots=True)
class LineageAdjacencyPage:
    direction: LineageDirection
    node_key: str
    edges: tuple[LineageEdge, ...]
    next_edge_key: str | None = None

    def __post_init__(self) -> None:
        if type(self.direction) is not LineageDirection:
            raise ValueError("direction must be LineageDirection")
        object.__setattr__(
            self, "node_key", require_lineage_key("node_key", self.node_key)
        )
        edges = tuple(self.edges)
        for edge in edges:
            if type(edge) is not LineageEdge:
                raise ValueError("edges must be LineageEdge")
        if len(edges) > LINEAGE_ADJACENCY_PAGE_MAX_EDGES:
            raise LineageError("lineage_record_oversize")
        if len({edge.edge_key for edge in edges}) != len(edges):
            raise LineageError("lineage_identity_conflict")
        object.__setattr__(self, "edges", edges)
        if self.next_edge_key is not None:
            object.__setattr__(
                self, "next_edge_key", require_lineage_cursor(self.next_edge_key)
            )


def encode_lineage_adjacency_page(page: LineageAdjacencyPage) -> bytes:
    if type(page) is not LineageAdjacencyPage:
        raise ValueError("page must be LineageAdjacencyPage")
    return _canonical(
        {
            "direction": page.direction.value,
            "edges": [
                _edge_payload(edge)
                for edge in sorted(page.edges, key=lambda item: item.edge_key)
            ],
            "next_edge_key": page.next_edge_key,
            "node_key": page.node_key,
        }
    )


def decode_lineage_adjacency_page(payload: bytes) -> LineageAdjacencyPage:
    document = _exact(
        _decode_json(payload, max_bytes=LINEAGE_RECORD_MAX_BYTES),
        frozenset({"direction", "edges", "next_edge_key", "node_key"}),
    )
    edges = document["edges"]
    if not isinstance(edges, list) or len(edges) > LINEAGE_ADJACENCY_PAGE_MAX_EDGES:
        raise LineageError("lineage_record_oversize")
    return LineageAdjacencyPage(
        direction=LineageDirection(str(document["direction"])),
        node_key=str(document["node_key"]),
        edges=tuple(_edge_decode(item) for item in edges),
        next_edge_key=_optional_cursor(document["next_edge_key"]),
    )


@dataclass(frozen=True, slots=True)
class LineageControlRecord:
    schema_version: str
    run_id: RunId
    catalogue_generation: str
    committed_publication_id: str
    committed_digest: str
    quota_reservations: int
    quota_artifact_bytes: int

    def __post_init__(self) -> None:
        if self.schema_version != LINEAGE_CONTROL_SCHEMA_VERSION:
            raise LineageError("unsupported_lineage_schema")
        if type(self.run_id) is not RunId:
            raise ValueError("control run_id must be RunId")
        for name in ("catalogue_generation",):
            object.__setattr__(self, name, require_stable_id(name, getattr(self, name)))
        object.__setattr__(
            self, "committed_publication_id", _digest(self.committed_publication_id)
        )
        object.__setattr__(self, "committed_digest", _digest(self.committed_digest))
        for name in ("quota_reservations", "quota_artifact_bytes"):
            object.__setattr__(
                self, name, require_exact_nonneg_int(name, getattr(self, name))
            )


def _control_payload(record: LineageControlRecord) -> dict[str, object]:
    return {
        "catalogue_generation": record.catalogue_generation,
        "committed_digest": record.committed_digest,
        "committed_publication_id": record.committed_publication_id,
        "quota_artifact_bytes": record.quota_artifact_bytes,
        "quota_reservations": record.quota_reservations,
        "run_id": record.run_id.value,
        "schema_version": record.schema_version,
    }


def encode_lineage_control_record(record: LineageControlRecord) -> bytes:
    if type(record) is not LineageControlRecord:
        raise ValueError("record must be LineageControlRecord")
    return _canonical(_control_payload(record))


def decode_lineage_control_record(payload: bytes) -> LineageControlRecord:
    document = _exact(
        _decode_json(payload, max_bytes=LINEAGE_RECORD_MAX_BYTES),
        frozenset(
            {
                "catalogue_generation",
                "committed_digest",
                "committed_publication_id",
                "quota_artifact_bytes",
                "quota_reservations",
                "run_id",
                "schema_version",
            }
        ),
    )
    return LineageControlRecord(
        schema_version=str(document["schema_version"]),
        run_id=RunId(str(document["run_id"])),
        catalogue_generation=str(document["catalogue_generation"]),
        committed_publication_id=str(document["committed_publication_id"]),
        committed_digest=str(document["committed_digest"]),
        quota_reservations=_nonneg(document["quota_reservations"]),
        quota_artifact_bytes=_nonneg(document["quota_artifact_bytes"]),
    )


def _publication_payload(
    publication: LineagePublication,
) -> tuple[dict[str, bytes], LineageSnapshotManifest]:
    nodes = publication.frame.nodes
    edges = publication.frame.edges
    files: dict[str, bytes] = {}
    node_pages: list[str] = []
    for index in range(0, len(nodes), LINEAGE_NODE_PAGE_MAX_NODES):
        node_page = LineageNodePage(
            nodes=nodes[index : index + LINEAGE_NODE_PAGE_MAX_NODES]
        )
        name = f"nodes/{index // LINEAGE_NODE_PAGE_MAX_NODES:04d}.json"
        files[name] = encode_lineage_node_page(node_page)
        node_pages.append(name)
    by_node: dict[str, list[LineageEdge]] = {}
    for edge in edges:
        by_node.setdefault(edge.source_key, []).append(edge)
        by_node.setdefault(edge.target_key, []).append(edge)
    for node_key in sorted(by_node):
        node_edges = sorted(
            by_node[node_key],
            key=lambda edge: (edge.observed_tick or 0, edge.edge_key),
        )
        for index in range(0, len(node_edges), LINEAGE_ADJACENCY_PAGE_MAX_EDGES):
            adjacency_page = LineageAdjacencyPage(
                direction=LineageDirection.BOTH,
                node_key=node_key,
                edges=tuple(
                    node_edges[index : index + LINEAGE_ADJACENCY_PAGE_MAX_EDGES]
                ),
            )
            page_index = index // LINEAGE_ADJACENCY_PAGE_MAX_EDGES
            files[f"adjacency/{node_key}-{page_index:04d}.json"] = (
                encode_lineage_adjacency_page(adjacency_page)
            )
    page_digests = tuple(
        (name, hashlib.sha256(content).hexdigest())
        for name, content in sorted(files.items())
    )
    manifest = LineageSnapshotManifest(
        run_id=publication.frame.run_id,
        family=publication.frame.scope.family,
        evidence_class=publication.frame.scope.evidence_class,
        owner_id=publication.frame.scope.owner_id,
        boundary_tick=publication.frame.boundary_tick,
        publication_id="0" * 64,
        content_digest=publication.snapshot.digest,
        source_revision=publication.frame.source_revision,
        policy_version=(
            publication.frame.coverage.policy_version or "lineage-snapshot-v1"
        ),
        coverage=publication.frame.coverage,
        node_count=len(nodes),
        edge_count=len(edges),
        page_count=len(files),
        page_digests=page_digests,
    )
    manifest = replace(manifest, publication_id=compute_publication_id(manifest))
    files["manifest.json"] = encode_lineage_manifest(manifest)
    return files, manifest


def encode_lineage_publication(publication: LineagePublication) -> dict[str, bytes]:
    if type(publication) is not LineagePublication:
        raise ValueError("publication must be LineagePublication")
    files, _manifest = _publication_payload(publication)
    return files


def decode_lineage_publication(files: Mapping[str, bytes]) -> LineagePublication:
    if not isinstance(files, Mapping) or "manifest.json" not in files:
        raise ValueError("lineage_record_invalid")
    manifest = decode_lineage_manifest(files["manifest.json"])
    if (
        manifest.node_count > CAPTURE_MAX_NODES
        or manifest.edge_count > CAPTURE_MAX_EDGES
    ):
        raise LineageError("lineage_record_oversize")
    if manifest.page_count != len(files) - 1:
        raise LineageError("lineage_digest_mismatch")
    for path, digest in manifest.page_digests:
        if path not in files:
            raise LineageError("lineage_digest_mismatch")
        if hashlib.sha256(files[path]).hexdigest() != digest:
            raise LineageError("lineage_digest_mismatch")
    nodes: list[LineageNode] = []
    edges: list[LineageEdge] = []
    seen_edge_keys: set[str] = set()
    for path in sorted(files):
        if path == "manifest.json":
            continue
        if path.startswith("nodes/"):
            node_page = decode_lineage_node_page(files[path])
            nodes.extend(node_page.nodes)
        elif path.startswith("adjacency/"):
            adjacency_page = decode_lineage_adjacency_page(files[path])
            for edge in adjacency_page.edges:
                if edge.edge_key not in seen_edge_keys:
                    seen_edge_keys.add(edge.edge_key)
                    edges.append(edge)
        else:
            raise ValueError("lineage_record_invalid")
    if len(nodes) != manifest.node_count or len(edges) != manifest.edge_count:
        raise LineageError("lineage_digest_mismatch")
    scope = LineageScope(
        run_id=manifest.run_id,
        family=manifest.family,
        evidence_class=manifest.evidence_class,
        owner_id=manifest.owner_id,
    )
    frame = LineageBoundaryFrame(
        run_id=manifest.run_id,
        scope=scope,
        boundary_tick=manifest.boundary_tick,
        observed_boundary=manifest.boundary_tick,
        nodes=tuple(nodes),
        edges=tuple(edges),
        coverage=manifest.coverage,
        source_revision=manifest.source_revision,
    )
    snapshot = LineageSnapshotRef(
        publication_id=manifest.publication_id,
        digest=manifest.content_digest,
        boundary_tick=manifest.boundary_tick,
    )
    return LineagePublication(snapshot=snapshot, frame=frame)
