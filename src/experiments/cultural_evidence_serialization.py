"""Canonical, duplicate-aware codec for normalized cultural evidence."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.cultural_evolution_evidence import (
    ArchiveKnowledgeState,
    CulturalAnalysisWindow,
    CulturalEvolutionInputs,
    EvidencePointer,
    GroupMembership,
    InventoryBoundary,
    TraitPresence,
    TransmissionEdge,
)
from simulation.cultural_evidence import CulturalCaptureStatus
from world.identifiers import require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.cultural_evidence_serialization"
)

CULTURAL_EVOLUTION_EVIDENCE_SCHEMA_VERSION: Final[str] = (
    "cultural-evolution-evidence-v1"
)
MAX_EVIDENCE_BYTES: Final[int] = 64 * 1024 * 1024
MAX_EVIDENCE_ROWS: Final[int] = 1_000_000
MAX_EVIDENCE_DEPTH: Final[int] = 32

_BOUNDARY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "boundary_tick",
        "living_owner_ids",
        "generation_by_owner",
        "owner_dimension_coverage",
    }
)
_TRAIT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "boundary_tick",
        "owner_id",
        "local_entry_id",
        "dimension",
        "content_digest",
        "lineage_key",
        "acquisition_tick",
        "parent_refs",
        "source_refs",
        "status",
    }
)
_EDGE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "edge_id",
        "source_owner_id",
        "receiver_owner_id",
        "source_local_id",
        "receiver_local_id",
        "acquisition_boundary",
        "modality",
        "attribution_status",
        "generation_class",
        "kin_vertical",
        "source_digest",
        "target_digest",
        "mutated",
        "recombined",
        "evidence_ids",
    }
)
_GROUP_KEYS: Final[frozenset[str]] = frozenset(
    {
        "boundary_tick",
        "owner_id",
        "group_id",
        "basis_id",
        "basis_version",
        "evidence_ids",
    }
)
_ARCHIVE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "boundary_tick",
        "subject_id",
        "content_digest",
        "record_present",
        "holder_owner_ids",
        "provenance_source_ids",
        "evidence_ids",
    }
)
_POINTER_KEYS: Final[frozenset[str]] = frozenset(
    {
        "run_id",
        "owner_id",
        "boundary_tick",
        "source_kind",
        "local_id",
        "source_revision_digest",
        "original_refs",
    }
)
_STATUS_KEYS: Final[frozenset[str]] = frozenset(
    {
        "active",
        "failed",
        "failure_boundary",
        "failure_code",
        "missing_prefix_through",
    }
)
_WINDOW_KEYS: Final[frozenset[str]] = frozenset({"baseline_boundary", "end_boundary"})

_ENVELOPE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "run_id",
        "config_fingerprint",
        "source_revision",
        "policy_version",
        "capture_options",
        "analysis_window",
        "boundaries",
        "trait_rows",
        "transmission_edges",
        "group_memberships",
        "archive_states",
        "evidence_pointers",
        "gaps",
        "capture_status",
        "digest",
    }
)

__all__ = [
    "CULTURAL_EVOLUTION_EVIDENCE_SCHEMA_VERSION",
    "CulturalEvidenceSerializationError",
    "CulturalEvolutionEvidence",
    "decode_cultural_evolution_evidence",
    "encode_cultural_evolution_evidence",
    "evidence_digest",
]


class CulturalEvidenceSerializationError(ValueError):
    """Payload-free codec failure with a stable safe code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CulturalEvolutionEvidence:
    """Decoded evidence envelope plus its verified canonical digest."""

    inputs: CulturalEvolutionInputs
    config_fingerprint: str
    capture_options: Mapping[str, object]
    capture_status: CulturalCaptureStatus
    digest: str

    def __repr__(self) -> str:
        return (
            f"CulturalEvolutionEvidence(run_id={self.inputs.run_id!r}, "
            f"schema_version={CULTURAL_EVOLUTION_EVIDENCE_SCHEMA_VERSION!r}, "
            f"boundary_count={len(self.inputs.boundaries)}, "
            f"edge_count={len(self.inputs.transmission_edges)}, "
            f"digest={self.digest[:12]!r})"
        )


def _canonical_json(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _digest_payload(payload: Mapping[str, object]) -> str:
    body = {key: value for key, value in payload.items() if key != "digest"}
    return hashlib.sha256(_canonical_json(body)).hexdigest()


def _codec_fail(code: str) -> CulturalEvidenceSerializationError:
    _LOG.error("cultural_evidence_codec_failed reason_code=%s", code)
    return CulturalEvidenceSerializationError(code)


def _require_sequence(value: object, code: str) -> Sequence[object]:
    if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, Sequence):
        raise _codec_fail(code)
    return value


def _require_mapping(value: object, code: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _codec_fail(code)
    for key in value:
        if not isinstance(key, str):
            raise _codec_fail(code)
    return value


def _require_exact_keys(
    value: Mapping[str, object],
    keys: frozenset[str],
    code: str,
) -> Mapping[str, object]:
    if set(value) != keys:
        raise _codec_fail(code)
    return value


def _depth_ok(data: bytes) -> bool:
    depth = 0
    quoted = False
    escaped = False
    for byte in data:
        char = chr(byte)
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char in "{[":
            depth += 1
            if depth > MAX_EVIDENCE_DEPTH:
                return False
        elif char in "}]":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _require_str(value: object, code: str) -> str:
    if not isinstance(value, str):
        raise _codec_fail(code)
    return value


def _require_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _codec_fail(code)
    return value


def _require_str_tuple(value: object, code: str) -> tuple[str, ...]:
    return tuple(_require_str(item, code) for item in _require_sequence(value, code))


def _require_optional_str(value: object, code: str) -> str | None:
    if value is None:
        return None
    return _require_str(value, code)


def _encode_boundary(boundary: InventoryBoundary) -> dict[str, object]:
    return {
        "boundary_tick": boundary.boundary_tick,
        "living_owner_ids": list(boundary.living_owner_ids),
        "generation_by_owner": dict(boundary.generation_by_owner),
        "owner_dimension_coverage": [
            [owner, dimension, coverage]
            for owner, dimension, coverage in boundary.owner_dimension_coverage
        ],
    }


def _encode_trait(boundary_tick: int, row: TraitPresence) -> dict[str, object]:
    return {
        "boundary_tick": boundary_tick,
        "owner_id": row.owner_id,
        "local_entry_id": row.local_entry_id,
        "dimension": row.dimension,
        "content_digest": row.content_digest,
        "lineage_key": row.lineage_key,
        "acquisition_tick": row.acquisition_tick,
        "parent_refs": list(row.parent_refs),
        "source_refs": list(row.source_refs),
        "status": row.status,
    }


def _encode_edge(edge: TransmissionEdge) -> dict[str, object]:
    return {
        "edge_id": edge.edge_id,
        "source_owner_id": edge.source_owner_id,
        "receiver_owner_id": edge.receiver_owner_id,
        "source_local_id": edge.source_local_id,
        "receiver_local_id": edge.receiver_local_id,
        "acquisition_boundary": edge.acquisition_boundary,
        "modality": edge.modality,
        "attribution_status": edge.attribution_status,
        "generation_class": edge.generation_class,
        "kin_vertical": edge.kin_vertical,
        "source_digest": edge.source_digest,
        "target_digest": edge.target_digest,
        "mutated": edge.mutated,
        "recombined": edge.recombined,
        "evidence_ids": list(edge.evidence_ids),
    }


def _encode_group(group: GroupMembership) -> dict[str, object]:
    return {
        "boundary_tick": group.boundary_tick,
        "owner_id": group.owner_id,
        "group_id": group.group_id,
        "basis_id": group.basis_id,
        "basis_version": group.basis_version,
        "evidence_ids": list(group.evidence_ids),
    }


def _encode_archive(archive: ArchiveKnowledgeState) -> dict[str, object]:
    return {
        "boundary_tick": archive.boundary_tick,
        "subject_id": archive.subject_id,
        "content_digest": archive.content_digest,
        "record_present": archive.record_present,
        "holder_owner_ids": list(archive.holder_owner_ids),
        "provenance_source_ids": list(archive.provenance_source_ids),
        "evidence_ids": list(archive.evidence_ids),
    }


def _encode_pointer(pointer: EvidencePointer) -> dict[str, object]:
    return {
        "run_id": pointer.run_id,
        "owner_id": pointer.owner_id,
        "boundary_tick": pointer.boundary_tick,
        "source_kind": pointer.source_kind,
        "local_id": pointer.local_id,
        "source_revision_digest": pointer.source_revision_digest,
        "original_refs": list(pointer.original_refs),
    }


def _encode_status(status: CulturalCaptureStatus) -> dict[str, object]:
    return {
        "active": status.active,
        "failed": status.failed,
        "failure_boundary": status.failure_boundary,
        "failure_code": status.failure_code,
        "missing_prefix_through": status.missing_prefix_through,
    }


def encode_cultural_evolution_evidence(
    inputs: CulturalEvolutionInputs,
    *,
    config_fingerprint: str,
    capture_options: Mapping[str, object],
    capture_status: CulturalCaptureStatus,
) -> bytes:
    """Encode the exact-key envelope with a canonical digest."""
    if type(inputs) is not CulturalEvolutionInputs:
        raise TypeError("inputs must be CulturalEvolutionInputs")
    fingerprint = require_stable_id("config_fingerprint", config_fingerprint)
    options = dict(capture_options)
    _canonical_json(options)
    payload: dict[str, object] = {
        "schema_version": CULTURAL_EVOLUTION_EVIDENCE_SCHEMA_VERSION,
        "run_id": inputs.run_id,
        "config_fingerprint": fingerprint,
        "source_revision": inputs.source_revision,
        "policy_version": inputs.policy_version,
        "capture_options": options,
        "analysis_window": {
            "baseline_boundary": inputs.window.baseline_boundary,
            "end_boundary": inputs.window.end_boundary,
        },
        "boundaries": [_encode_boundary(boundary) for boundary in inputs.boundaries],
        "trait_rows": [
            _encode_trait(boundary.boundary_tick, row)
            for boundary in inputs.boundaries
            for row in boundary.entries
        ],
        "transmission_edges": [
            _encode_edge(edge) for edge in inputs.transmission_edges
        ],
        "group_memberships": [
            _encode_group(group) for group in inputs.group_memberships
        ],
        "archive_states": [
            _encode_archive(archive) for archive in inputs.archive_states
        ],
        "evidence_pointers": [
            _encode_pointer(pointer) for pointer in inputs.evidence_pointers
        ],
        "gaps": list(inputs.gaps),
        "capture_status": _encode_status(capture_status),
    }
    payload["digest"] = _digest_payload(payload)
    body = _canonical_json(payload)
    if len(body) > MAX_EVIDENCE_BYTES:
        raise _codec_fail("too_large")
    _LOG.debug(
        "cultural_evidence_encoded run_id=%s boundary_count=%s edge_count=%s "
        "trait_row_count=%s",
        inputs.run_id,
        len(inputs.boundaries),
        len(inputs.transmission_edges),
        sum(len(boundary.entries) for boundary in inputs.boundaries),
    )
    return body


def evidence_digest(
    inputs: CulturalEvolutionInputs,
    *,
    config_fingerprint: str,
    capture_options: Mapping[str, object],
    capture_status: CulturalCaptureStatus,
) -> str:
    """Return the canonical evidence digest without retaining encoded bytes."""
    import json as _json

    body = encode_cultural_evolution_evidence(
        inputs,
        config_fingerprint=config_fingerprint,
        capture_options=capture_options,
        capture_status=capture_status,
    )
    return str(_json.loads(body.decode("utf-8"))["digest"])


def _duplicate_aware_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _codec_fail("duplicate_key")
        result[key] = value
    return result


def _decode_trait(row: Mapping[str, object]) -> tuple[int, TraitPresence]:
    _require_exact_keys(row, _TRAIT_KEYS, "invalid_trait_row")
    boundary_tick = _require_int(row.get("boundary_tick"), "invalid_trait_row")
    presence = TraitPresence(
        owner_id=_require_str(row.get("owner_id"), "invalid_trait_row"),
        local_entry_id=_require_str(row.get("local_entry_id"), "invalid_trait_row"),
        dimension=_require_str(row.get("dimension"), "invalid_trait_row"),
        content_digest=_require_str(row.get("content_digest"), "invalid_trait_row"),
        lineage_key=_require_optional_str(row.get("lineage_key"), "invalid_trait_row"),
        acquisition_tick=(
            None
            if row.get("acquisition_tick") is None
            else _require_int(row.get("acquisition_tick"), "invalid_trait_row")
        ),
        parent_refs=_require_str_tuple(row.get("parent_refs"), "invalid_trait_row"),
        source_refs=_require_str_tuple(row.get("source_refs"), "invalid_trait_row"),
        status=_require_optional_str(row.get("status"), "invalid_trait_row"),
    )
    return boundary_tick, presence


def decode_cultural_evolution_evidence(data: bytes) -> CulturalEvolutionEvidence:
    """Decode and verify a canonical evidence envelope."""
    if not isinstance(data, bytes) or len(data) > MAX_EVIDENCE_BYTES:
        raise _codec_fail("too_large")
    if not _depth_ok(data):
        raise _codec_fail("excessive_depth")
    try:
        payload = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_duplicate_aware_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                CulturalEvidenceSerializationError("nonfinite_number")
            ),
        )
    except CulturalEvidenceSerializationError:
        raise
    except Exception as exc:
        raise _codec_fail("invalid_json") from exc
    document = _require_mapping(payload, "invalid_envelope")
    if set(document) != _ENVELOPE_KEYS:
        raise _codec_fail("key_set_mismatch")
    if document.get("schema_version") != CULTURAL_EVOLUTION_EVIDENCE_SCHEMA_VERSION:
        raise _codec_fail("unsupported_schema")
    if document.get("digest") != _digest_payload(document):
        raise _codec_fail("digest_mismatch")

    window_doc = _require_exact_keys(
        _require_mapping(document.get("analysis_window"), "invalid_window"),
        _WINDOW_KEYS,
        "invalid_window",
    )
    window = CulturalAnalysisWindow(
        baseline_boundary=_require_int(
            window_doc.get("baseline_boundary"), "invalid_window"
        ),
        end_boundary=(
            None
            if window_doc.get("end_boundary") is None
            else _require_int(window_doc.get("end_boundary"), "invalid_window")
        ),
    )
    raw_boundaries = _require_sequence(document.get("boundaries"), "invalid_boundaries")
    raw_traits = _require_sequence(document.get("trait_rows"), "invalid_trait_rows")
    if len(raw_boundaries) + len(raw_traits) > MAX_EVIDENCE_ROWS:
        raise _codec_fail("row_limit")
    traits_by_boundary: dict[int, list[TraitPresence]] = {}
    for raw in raw_traits:
        boundary_tick, presence = _decode_trait(
            _require_mapping(raw, "invalid_trait_row")
        )
        traits_by_boundary.setdefault(boundary_tick, []).append(presence)
    boundaries: list[InventoryBoundary] = []
    for raw in raw_boundaries:
        row = _require_exact_keys(
            _require_mapping(raw, "invalid_boundary"),
            _BOUNDARY_KEYS,
            "invalid_boundary",
        )
        boundary_tick = _require_int(row.get("boundary_tick"), "invalid_boundary")
        generations = _require_mapping(
            row.get("generation_by_owner"), "invalid_boundary"
        )
        coverage = _require_sequence(
            row.get("owner_dimension_coverage"), "invalid_boundary"
        )
        normalized_coverage: list[tuple[str, str, str]] = []
        for item in coverage:
            triple = _require_sequence(item, "invalid_boundary")
            if len(triple) != 3:
                raise _codec_fail("invalid_boundary")
            normalized_coverage.append(
                (
                    _require_str(triple[0], "invalid_boundary"),
                    _require_str(triple[1], "invalid_boundary"),
                    _require_str(triple[2], "invalid_boundary"),
                )
            )
        boundaries.append(
            InventoryBoundary(
                boundary_tick=boundary_tick,
                living_owner_ids=_require_str_tuple(
                    row.get("living_owner_ids"), "invalid_boundary"
                ),
                generation_by_owner={
                    _require_str(key, "invalid_boundary"): _require_int(
                        value, "invalid_boundary"
                    )
                    for key, value in generations.items()
                },
                owner_dimension_coverage=tuple(normalized_coverage),
                entries=tuple(traits_by_boundary.get(boundary_tick, ())),
            )
        )

    edges: list[TransmissionEdge] = []
    for raw in _require_sequence(document.get("transmission_edges"), "invalid_edges"):
        row = _require_exact_keys(
            _require_mapping(raw, "invalid_edge"), _EDGE_KEYS, "invalid_edge"
        )
        edges.append(
            TransmissionEdge(
                edge_id=_require_str(row.get("edge_id"), "invalid_edge"),
                source_owner_id=_require_optional_str(
                    row.get("source_owner_id"), "invalid_edge"
                ),
                receiver_owner_id=_require_str(
                    row.get("receiver_owner_id"), "invalid_edge"
                ),
                source_local_id=_require_optional_str(
                    row.get("source_local_id"), "invalid_edge"
                ),
                receiver_local_id=_require_str(
                    row.get("receiver_local_id"), "invalid_edge"
                ),
                acquisition_boundary=_require_int(
                    row.get("acquisition_boundary"), "invalid_edge"
                ),
                modality=_require_str(row.get("modality"), "invalid_edge"),
                attribution_status=_require_str(
                    row.get("attribution_status"), "invalid_edge"
                ),
                generation_class=_require_str(
                    row.get("generation_class"), "invalid_edge"
                ),
                kin_vertical=bool(row.get("kin_vertical")),
                source_digest=_require_optional_str(
                    row.get("source_digest"), "invalid_edge"
                ),
                target_digest=_require_optional_str(
                    row.get("target_digest"), "invalid_edge"
                ),
                mutated=bool(row.get("mutated")),
                recombined=bool(row.get("recombined")),
                evidence_ids=_require_str_tuple(
                    row.get("evidence_ids"), "invalid_edge"
                ),
            )
        )

    groups: list[GroupMembership] = []
    for raw in _require_sequence(document.get("group_memberships"), "invalid_groups"):
        row = _require_exact_keys(
            _require_mapping(raw, "invalid_group"), _GROUP_KEYS, "invalid_group"
        )
        groups.append(
            GroupMembership(
                boundary_tick=_require_int(row.get("boundary_tick"), "invalid_group"),
                owner_id=_require_str(row.get("owner_id"), "invalid_group"),
                group_id=_require_str(row.get("group_id"), "invalid_group"),
                basis_id=_require_str(row.get("basis_id"), "invalid_group"),
                basis_version=_require_str(row.get("basis_version"), "invalid_group"),
                evidence_ids=_require_str_tuple(
                    row.get("evidence_ids"), "invalid_group"
                ),
            )
        )

    archives: list[ArchiveKnowledgeState] = []
    for raw in _require_sequence(document.get("archive_states"), "invalid_archives"):
        row = _require_exact_keys(
            _require_mapping(raw, "invalid_archive"), _ARCHIVE_KEYS, "invalid_archive"
        )
        archives.append(
            ArchiveKnowledgeState(
                boundary_tick=_require_int(row.get("boundary_tick"), "invalid_archive"),
                subject_id=_require_str(row.get("subject_id"), "invalid_archive"),
                content_digest=_require_str(
                    row.get("content_digest"), "invalid_archive"
                ),
                record_present=bool(row.get("record_present")),
                holder_owner_ids=_require_str_tuple(
                    row.get("holder_owner_ids"), "invalid_archive"
                ),
                provenance_source_ids=_require_str_tuple(
                    row.get("provenance_source_ids"), "invalid_archive"
                ),
                evidence_ids=_require_str_tuple(
                    row.get("evidence_ids"), "invalid_archive"
                ),
            )
        )

    pointers: list[EvidencePointer] = []
    for raw in _require_sequence(document.get("evidence_pointers"), "invalid_pointers"):
        row = _require_exact_keys(
            _require_mapping(raw, "invalid_pointer"), _POINTER_KEYS, "invalid_pointer"
        )
        pointers.append(
            EvidencePointer(
                run_id=_require_str(row.get("run_id"), "invalid_pointer"),
                owner_id=_require_optional_str(row.get("owner_id"), "invalid_pointer"),
                boundary_tick=_require_int(row.get("boundary_tick"), "invalid_pointer"),
                source_kind=_require_str(row.get("source_kind"), "invalid_pointer"),
                local_id=_require_optional_str(row.get("local_id"), "invalid_pointer"),
                source_revision_digest=_require_optional_str(
                    row.get("source_revision_digest"), "invalid_pointer"
                ),
                original_refs=_require_str_tuple(
                    row.get("original_refs"), "invalid_pointer"
                ),
            )
        )

    status_doc = _require_exact_keys(
        _require_mapping(document.get("capture_status"), "invalid_capture_status"),
        _STATUS_KEYS,
        "invalid_capture_status",
    )
    capture_status = CulturalCaptureStatus(
        active=bool(status_doc.get("active")),
        failed=bool(status_doc.get("failed")),
        failure_boundary=(
            None
            if status_doc.get("failure_boundary") is None
            else _require_int(
                status_doc.get("failure_boundary"), "invalid_capture_status"
            )
        ),
        failure_code=_require_optional_str(
            status_doc.get("failure_code"), "invalid_capture_status"
        ),
        missing_prefix_through=(
            None
            if status_doc.get("missing_prefix_through") is None
            else _require_int(
                status_doc.get("missing_prefix_through"),
                "invalid_capture_status",
            )
        ),
    )
    inputs = CulturalEvolutionInputs(
        run_id=_require_str(document.get("run_id"), "invalid_envelope"),
        source_revision=_require_str(
            document.get("source_revision"), "invalid_envelope"
        ),
        window=window,
        boundaries=tuple(boundaries),
        transmission_edges=tuple(edges),
        group_memberships=tuple(groups),
        archive_states=tuple(archives),
        evidence_pointers=tuple(pointers),
        gaps=_require_str_tuple(document.get("gaps"), "invalid_envelope"),
        policy_version=_require_str(document.get("policy_version"), "invalid_envelope"),
    )
    envelope = CulturalEvolutionEvidence(
        inputs=inputs,
        config_fingerprint=_require_str(
            document.get("config_fingerprint"), "invalid_envelope"
        ),
        capture_options=dict(
            _require_mapping(document.get("capture_options"), "invalid_envelope")
        ),
        capture_status=capture_status,
        digest=_require_str(document.get("digest"), "invalid_envelope"),
    )
    _LOG.debug(
        "cultural_evidence_decoded run_id=%s boundary_count=%s edge_count=%s",
        inputs.run_id,
        len(inputs.boundaries),
        len(inputs.transmission_edges),
    )
    return envelope
