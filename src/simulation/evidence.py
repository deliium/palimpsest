"""Simulation-owned immutable evidence manifests and high-water helpers.

Manifests constrain repeatable-read loading for metric computation. They carry
counts and hashes only — never truth payloads, claims, or source rows.

Must not import ``analysis`` or ``experiments``.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Protocol

from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "EVIDENCE_MANIFEST_SCHEMA_VERSION",
    "EvidenceHighWaterMarks",
    "EvidenceManifest",
    "EvidenceManifestError",
    "EvidenceManifestReader",
    "build_evidence_manifest",
    "clamp_sequence_to_high_water",
    "manifest_hash_prefix",
    "manifest_idempotency_material",
]

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
