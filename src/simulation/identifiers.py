"""Deterministic namespaced identifiers.

IDs are derived with SHA-256 over canonical bytes. Python's builtin
object hashing is never used. Operational HTTP/log metadata cannot
populate these values.
"""

from __future__ import annotations

import hashlib

from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.randomness import StreamScope, canonical_scope_bytes


def _digest(*parts: bytes) -> bytes:
    hasher = hashlib.sha256()
    hasher.update(DERIVATION_VERSION.encode("utf-8"))
    for part in parts:
        hasher.update(len(part).to_bytes(4, "big"))
        hasher.update(part)
    return hasher.digest()


def derive_run_id(config: SimulationRunConfig) -> RunId:
    """Derive a stable run id from the canonical seed and derivation version."""
    digest = _digest(b"run", str(config.seed).encode("utf-8"))
    return RunId(digest.hex())


def derive_scoped_id(config: SimulationRunConfig, scope: StreamScope) -> str:
    """Derive a namespaced id that does not alias distinct scopes."""
    digest = _digest(
        b"id", str(config.seed).encode("utf-8"), canonical_scope_bytes(scope)
    )
    return digest.hex()


def reject_operational_identifier(source: str, value: str) -> None:
    """Refuse HTTP/log correlation values as simulation identifiers."""
    raise TypeError(
        f"{source} is operational metadata and cannot populate domain identifiers "
        f"(rejected value length {len(value)})"
    )
