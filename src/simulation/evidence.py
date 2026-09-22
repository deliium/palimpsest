"""Simulation-owned immutable evidence manifests and high-water helpers.

Manifests constrain repeatable-read loading for metric computation. They carry
counts and hashes only — never truth payloads, claims, or source rows.

Also owns opaque codecs for goal revisions and action-resolution evidence so
persistence can store canonical bytes/hashes without importing analysis types.

Must not import ``analysis`` or ``experiments``.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Protocol

from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "ACTION_RESOLUTION_SCHEMA_VERSION",
    "EVIDENCE_MANIFEST_SCHEMA_VERSION",
    "GOAL_REVISION_SCHEMA_VERSION",
    "ActionResolutionRecord",
    "EvidenceHighWaterMarks",
    "EvidenceManifest",
    "EvidenceManifestError",
    "EvidenceManifestReader",
    "GoalRevisionRecord",
    "OpaqueCanonicalEnvelope",
    "build_evidence_manifest",
    "clamp_sequence_to_high_water",
    "encode_action_resolution_evidence",
    "encode_evidence_manifest_payload",
    "encode_goal_transition_receipt",
    "hash_canonical_payload",
    "manifest_hash_prefix",
    "manifest_idempotency_material",
    "opaque_envelope_from_payload",
]

GOAL_REVISION_SCHEMA_VERSION: Final[str] = "goal-revision-v1"
ACTION_RESOLUTION_SCHEMA_VERSION: Final[str] = "action-resolution-v1"

_LOG: Final[logging.Logger] = logging.getLogger("simulation.evidence")

EVIDENCE_MANIFEST_SCHEMA_VERSION: Final[str] = "evidence-manifest-v1"


class EvidenceManifestError(ValueError):
    """Stable failure for manifest schema, scope, or version violations."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class EvidenceHighWaterMarks:
    """Per-source inclusive high-water counts for one evidence revision."""

    direct_memories: int
    communicated_memories: int
    reconstructions: int
    beliefs: int
    relationships: int
    goals: int
    resolutions: int
    truth_specs: int

    def __post_init__(self) -> None:
        for field_name in (
            "direct_memories",
            "communicated_memories",
            "reconstructions",
            "beliefs",
            "relationships",
            "goals",
            "resolutions",
            "truth_specs",
        ):
            object.__setattr__(
                self,
                field_name,
                require_exact_nonneg_int(
                    f"EvidenceHighWaterMarks.{field_name}",
                    getattr(self, field_name),
                ),
            )

    def as_canonical_dict(self) -> dict[str, int]:
        return {
            "beliefs": self.beliefs,
            "communicated_memories": self.communicated_memories,
            "direct_memories": self.direct_memories,
            "goals": self.goals,
            "reconstructions": self.reconstructions,
            "relationships": self.relationships,
            "resolutions": self.resolutions,
            "truth_specs": self.truth_specs,
        }

    def __repr__(self) -> str:
        return (
            "EvidenceHighWaterMarks("
            f"direct={self.direct_memories}, "
            f"communicated={self.communicated_memories}, "
            f"reconstructions={self.reconstructions}, "
            f"beliefs={self.beliefs}, "
            f"relationships={self.relationships}, "
            f"goals={self.goals}, "
            f"resolutions={self.resolutions}, "
            f"truth_specs={self.truth_specs})"
        )


@dataclass(frozen=True, slots=True)
class EvidenceManifest:
    """Immutable evidence revision bound to one run and objective commit."""

    schema_version: str
    run_id: str
    objective_commit_hash: str
    high_water: EvidenceHighWaterMarks
    manifest_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema_version",
            require_stable_id("EvidenceManifest.schema_version", self.schema_version),
        )
        if self.schema_version != EVIDENCE_MANIFEST_SCHEMA_VERSION:
            _LOG.error(
                "evidence_manifest_unsupported_version",
                extra={
                    "operation": "EvidenceManifest.__post_init__",
                    "reason_code": "unsupported_manifest_version",
                    "schema_version": self.schema_version,
                },
            )
            raise EvidenceManifestError("unsupported_manifest_version")
        object.__setattr__(
            self,
            "run_id",
            require_stable_id("EvidenceManifest.run_id", self.run_id),
        )
        object.__setattr__(
            self,
            "objective_commit_hash",
            require_stable_id(
                "EvidenceManifest.objective_commit_hash", self.objective_commit_hash
            ),
        )
        if type(self.high_water) is not EvidenceHighWaterMarks:
            raise TypeError("EvidenceManifest.high_water: invalid_type")
        object.__setattr__(
            self,
            "manifest_hash",
            require_stable_id("EvidenceManifest.manifest_hash", self.manifest_hash),
        )
        expected = _compute_manifest_hash(
            schema_version=self.schema_version,
            run_id=self.run_id,
            objective_commit_hash=self.objective_commit_hash,
            high_water=self.high_water,
        )
        if self.manifest_hash != expected:
            _LOG.error(
                "evidence_manifest_hash_mismatch",
                extra={
                    "operation": "EvidenceManifest.__post_init__",
                    "reason_code": "manifest_hash_mismatch",
                    "run_id": self.run_id,
                    "expected_prefix": expected[:12],
                    "actual_prefix": self.manifest_hash[:12],
                },
            )
            raise EvidenceManifestError("manifest_hash_mismatch")

    def __repr__(self) -> str:
        return (
            f"EvidenceManifest(schema_version={self.schema_version!r}, "
            f"run_id={self.run_id!r}, "
            f"objective_commit_prefix={self.objective_commit_hash[:12]!r}, "
            f"manifest_hash_prefix={self.manifest_hash[:12]!r}, "
            f"high_water={self.high_water!r})"
        )


class EvidenceManifestReader(Protocol):
    """Load evidence under one immutable manifest (repeatable-read scope).

    Implementations must clamp/filter every source to ``manifest.high_water``
    and must not return rows beyond those marks.
    """

    def load_constrained_to_manifest(self, manifest: EvidenceManifest) -> object:
        """Return a detached evidence bundle constrained to ``manifest``."""
        ...


def build_evidence_manifest(
    *,
    run_id: str,
    objective_commit_hash: str,
    high_water: EvidenceHighWaterMarks,
    schema_version: str = EVIDENCE_MANIFEST_SCHEMA_VERSION,
) -> EvidenceManifest:
    """Build a validated manifest with a canonical content hash."""
    _LOG.debug(
        "evidence_manifest_build_start",
        extra={
            "operation": "build_evidence_manifest",
            "run_id": run_id,
            "schema_version": schema_version,
            "objective_commit_prefix": _hash_prefix(objective_commit_hash),
            "high_water": high_water.as_canonical_dict(),
        },
    )
    digest = _compute_manifest_hash(
        schema_version=schema_version,
        run_id=run_id,
        objective_commit_hash=objective_commit_hash,
        high_water=high_water,
    )
    manifest = EvidenceManifest(
        schema_version=schema_version,
        run_id=run_id,
        objective_commit_hash=objective_commit_hash,
        high_water=high_water,
        manifest_hash=digest,
    )
    _LOG.debug(
        "evidence_manifest_build_complete",
        extra={
            "operation": "build_evidence_manifest",
            "run_id": manifest.run_id,
            "schema_version": manifest.schema_version,
            "manifest_hash_prefix": manifest_hash_prefix(manifest),
            "high_water": manifest.high_water.as_canonical_dict(),
            "transaction_status": "detached",
        },
    )
    return manifest


def clamp_sequence_to_high_water[T](
    items: Sequence[T],
    high_water: int,
    *,
    source_label: str,
) -> tuple[T, ...]:
    """Return the first ``high_water`` items from an ordered source sequence.

    Callers must supply sources already ordered by durable identity. Counts
    beyond the high-water mark are dropped; shortfall is warned as incomplete.
    """
    limit = require_exact_nonneg_int("high_water", high_water)
    sequence = tuple(items)
    if len(sequence) < limit:
        _LOG.warning(
            "evidence_source_incomplete_for_manifest",
            extra={
                "operation": "clamp_sequence_to_high_water",
                "source_label": source_label,
                "reason_code": "incomplete_evidence",
                "available_count": len(sequence),
                "high_water": limit,
            },
        )
        return sequence
    if len(sequence) > limit:
        _LOG.debug(
            "evidence_source_clamped_to_manifest",
            extra={
                "operation": "clamp_sequence_to_high_water",
                "source_label": source_label,
                "available_count": len(sequence),
                "high_water": limit,
            },
        )
    return sequence[:limit]


def manifest_idempotency_material(manifest: EvidenceManifest) -> str:
    """Stable material for metric idempotency keys (manifest hash input)."""
    if type(manifest) is not EvidenceManifest:
        raise TypeError("manifest_idempotency_material: invalid_type")
    return manifest.manifest_hash


def manifest_hash_prefix(manifest: EvidenceManifest, *, length: int = 12) -> str:
    """Return a log-safe prefix of the manifest hash."""
    if type(manifest) is not EvidenceManifest:
        raise TypeError("manifest_hash_prefix: invalid_type")
    if length < 1:
        raise EvidenceManifestError("invalid_hash_prefix_length")
    return manifest.manifest_hash[:length]


def _compute_manifest_hash(
    *,
    schema_version: str,
    run_id: str,
    objective_commit_hash: str,
    high_water: EvidenceHighWaterMarks,
) -> str:
    document = {
        "high_water": high_water.as_canonical_dict(),
        "objective_commit_hash": objective_commit_hash,
        "run_id": run_id,
        "schema_version": schema_version,
    }
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(payload).hexdigest()


def _hash_prefix(value: str, *, length: int = 12) -> str:
    if not isinstance(value, str) or not value:
        return ""
    return value[:length]


def _canonical_dumps(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def hash_canonical_payload(payload: bytes) -> str:
    """SHA-256 hex digest of opaque canonical bytes."""
    if type(payload) is not bytes:
        raise TypeError("payload must be bytes")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class OpaqueCanonicalEnvelope:
    """Schema-versioned opaque bytes with matching content hash.

    Persistence stores these without decoding. Analysis/simulation codecs
    produce the payload at the composition boundary.
    """

    schema_version: str
    content_hash: str
    payload: bytes

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema_version",
            require_stable_id(
                "OpaqueCanonicalEnvelope.schema_version", self.schema_version
            ),
        )
        if type(self.payload) is not bytes:
            raise TypeError("OpaqueCanonicalEnvelope.payload: invalid_type")
        object.__setattr__(
            self,
            "content_hash",
            require_stable_id(
                "OpaqueCanonicalEnvelope.content_hash", self.content_hash
            ),
        )
        expected = hash_canonical_payload(self.payload)
        if self.content_hash != expected:
            _LOG.error(
                "opaque_envelope_hash_mismatch",
                extra={
                    "operation": "OpaqueCanonicalEnvelope.__post_init__",
                    "reason_code": "content_hash_mismatch",
                    "schema_version": self.schema_version,
                    "expected_prefix": expected[:12],
                    "actual_prefix": self.content_hash[:12],
                },
            )
            raise EvidenceManifestError("content_hash_mismatch")

    def __repr__(self) -> str:
        return (
            f"OpaqueCanonicalEnvelope(schema_version={self.schema_version!r}, "
            f"content_hash_prefix={self.content_hash[:12]!r}, "
            f"payload_bytes={len(self.payload)})"
        )


def opaque_envelope_from_payload(
    *, schema_version: str, payload: bytes
) -> OpaqueCanonicalEnvelope:
    """Build a validated envelope from already-canonical payload bytes."""
    digest = hash_canonical_payload(payload)
    return OpaqueCanonicalEnvelope(
        schema_version=schema_version,
        content_hash=digest,
        payload=payload,
    )


@dataclass(frozen=True, slots=True)
class GoalRevisionRecord:
    """Append-only versioned goal transition (opaque payload + indexed keys)."""

    run_id: str
    goal_id: str
    revision: int
    owner_id: str
    tick: int
    envelope: OpaqueCanonicalEnvelope

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "run_id", require_stable_id("GoalRevisionRecord.run_id", self.run_id)
        )
        object.__setattr__(
            self,
            "goal_id",
            require_stable_id("GoalRevisionRecord.goal_id", self.goal_id),
        )
        object.__setattr__(
            self,
            "owner_id",
            require_stable_id("GoalRevisionRecord.owner_id", self.owner_id),
        )
        object.__setattr__(
            self,
            "revision",
            require_exact_nonneg_int("GoalRevisionRecord.revision", self.revision),
        )
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("GoalRevisionRecord.tick", self.tick),
        )
        if type(self.envelope) is not OpaqueCanonicalEnvelope:
            raise TypeError("GoalRevisionRecord.envelope: invalid_type")
        if self.envelope.schema_version != GOAL_REVISION_SCHEMA_VERSION:
            raise EvidenceManifestError("unsupported_goal_revision_version")

    def __repr__(self) -> str:
        return (
            f"GoalRevisionRecord(run_id={self.run_id!r}, goal_id={self.goal_id!r}, "
            f"revision={self.revision}, tick={self.tick}, "
            f"hash_prefix={self.envelope.content_hash[:12]!r})"
        )


@dataclass(frozen=True, slots=True)
class ActionResolutionRecord:
    """Append-only action resolution keyed by ``(run, tick, ordinal)``."""

    run_id: str
    tick: int
    ordinal: int
    envelope: OpaqueCanonicalEnvelope

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "run_id",
            require_stable_id("ActionResolutionRecord.run_id", self.run_id),
        )
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("ActionResolutionRecord.tick", self.tick),
        )
        object.__setattr__(
            self,
            "ordinal",
            require_exact_nonneg_int("ActionResolutionRecord.ordinal", self.ordinal),
        )
        if type(self.envelope) is not OpaqueCanonicalEnvelope:
            raise TypeError("ActionResolutionRecord.envelope: invalid_type")
        if self.envelope.schema_version != ACTION_RESOLUTION_SCHEMA_VERSION:
            raise EvidenceManifestError("unsupported_action_resolution_version")

    def __repr__(self) -> str:
        return (
            f"ActionResolutionRecord(run_id={self.run_id!r}, tick={self.tick}, "
            f"ordinal={self.ordinal}, "
            f"hash_prefix={self.envelope.content_hash[:12]!r})"
        )


def encode_goal_transition_receipt(receipt: object) -> OpaqueCanonicalEnvelope:
    """Encode a ``GoalTransitionReceipt`` as an opaque canonical envelope."""
    from simulation.runner_models import GoalTransitionReceipt

    if type(receipt) is not GoalTransitionReceipt:
        raise TypeError("encode_goal_transition_receipt requires GoalTransitionReceipt")
    document: dict[str, Any] = {
        "from_status": receipt.from_status.value,
        "goal_id": receipt.goal_id.value,
        "outcome_kind": receipt.outcome_kind.value,
        "owner_id": receipt.owner_id.value,
        "reason_code": receipt.reason_code.value,
        "schema_version": GOAL_REVISION_SCHEMA_VERSION,
        "tick": receipt.tick,
        "to_status": receipt.to_status.value,
    }
    payload = _canonical_dumps(document)
    envelope = opaque_envelope_from_payload(
        schema_version=GOAL_REVISION_SCHEMA_VERSION, payload=payload
    )
    _LOG.debug(
        "goal_revision_encoded",
        extra={
            "operation": "encode_goal_transition_receipt",
            "schema_version": GOAL_REVISION_SCHEMA_VERSION,
            "hash_prefix": envelope.content_hash[:12],
        },
    )
    return envelope


def encode_action_resolution_evidence(evidence: object) -> OpaqueCanonicalEnvelope:
    """Encode ``ActionResolutionEvidence`` as an opaque canonical envelope."""
    from simulation.runner_models import ActionResolutionEvidence

    if type(evidence) is not ActionResolutionEvidence:
        raise TypeError(
            "encode_action_resolution_evidence requires ActionResolutionEvidence"
        )
    document: dict[str, Any] = {
        "agent_id": evidence.agent_id.value,
        "base_revision": evidence.base_revision,
        "command_kind": evidence.command_kind,
        "ordinal": evidence.ordinal,
        "reason": evidence.reason.value,
        "request_id": evidence.request_id,
        "resulting_revision": evidence.resulting_revision,
        "schema_version": ACTION_RESOLUTION_SCHEMA_VERSION,
        "status": evidence.status.value,
        "tick": evidence.tick,
    }
    payload = _canonical_dumps(document)
    envelope = opaque_envelope_from_payload(
        schema_version=ACTION_RESOLUTION_SCHEMA_VERSION, payload=payload
    )
    _LOG.debug(
        "action_resolution_encoded",
        extra={
            "operation": "encode_action_resolution_evidence",
            "schema_version": ACTION_RESOLUTION_SCHEMA_VERSION,
            "tick": evidence.tick,
            "ordinal": evidence.ordinal,
            "hash_prefix": envelope.content_hash[:12],
        },
    )
    return envelope


def encode_evidence_manifest_payload(manifest: EvidenceManifest) -> bytes:
    """Canonical JSON bytes matching the manifest content-hash document."""
    if type(manifest) is not EvidenceManifest:
        raise TypeError("encode_evidence_manifest_payload requires EvidenceManifest")
    document: Mapping[str, object] = {
        "high_water": manifest.high_water.as_canonical_dict(),
        "objective_commit_hash": manifest.objective_commit_hash,
        "run_id": manifest.run_id,
        "schema_version": manifest.schema_version,
    }
    return _canonical_dumps(document)
