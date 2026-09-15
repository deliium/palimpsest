"""Deterministic namespaced identifiers.

IDs are derived with SHA-256 over canonical bytes. Python's builtin
object hashing is never used. Operational HTTP/log metadata cannot
populate these values.
"""

from __future__ import annotations

import hashlib

from agents.models import GoalId
from memory.models import BeliefId, MemoryId
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.randomness import StreamScope, canonical_scope_bytes
from social.models import EnvelopeId, RelationshipId
from world.identifiers import (
    EntityId,
    EventId,
    ProposalId,
    RequestId,
    WorldId,
)


def _digest(*parts: bytes) -> bytes:
    hasher = hashlib.sha256()
    hasher.update(DERIVATION_VERSION.encode("utf-8"))
    for part in parts:
        hasher.update(len(part).to_bytes(4, "big"))
        hasher.update(part)
    return hasher.digest()


def _require_canonical_keys(keys: tuple[str, ...]) -> None:
    if not keys:
        raise ValueError("canonical keys must contain at least one key")
    for key in keys:
        if not isinstance(key, str):
            raise TypeError("canonical keys must be str values")
        if key == "":
            raise ValueError("canonical keys must be non-empty strings")


def _derive_purpose_hex(
    purpose: bytes, config: SimulationRunConfig, *keys: str
) -> str:
    _require_canonical_keys(keys)
    return _digest(
        purpose,
        str(config.seed).encode("utf-8"),
        *(key.encode("utf-8") for key in keys),
    ).hex()


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


def derive_world_id(config: SimulationRunConfig, *keys: str) -> WorldId:
    """Derive a stable world aggregate id from seed and canonical keys."""
    return WorldId(_derive_purpose_hex(b"world", config, *keys))


def derive_entity_id(config: SimulationRunConfig, *keys: str) -> EntityId:
    """Derive a stable world entity id from seed and canonical keys."""
    return EntityId(_derive_purpose_hex(b"entity", config, *keys))


def derive_proposal_id(config: SimulationRunConfig, *keys: str) -> ProposalId:
    """Derive a stable proposal id from seed and canonical keys."""
    return ProposalId(_derive_purpose_hex(b"proposal", config, *keys))


def derive_request_id(config: SimulationRunConfig, *keys: str) -> RequestId:
    """Derive a stable request id from seed and canonical keys."""
    return RequestId(_derive_purpose_hex(b"request", config, *keys))


def derive_event_id(config: SimulationRunConfig, *keys: str) -> EventId:
    """Derive a stable event id from seed and canonical keys."""
    return EventId(_derive_purpose_hex(b"event", config, *keys))


def derive_goal_id(config: SimulationRunConfig, *keys: str) -> GoalId:
    """Derive a stable goal id from seed and canonical keys."""
    return GoalId(_derive_purpose_hex(b"goal", config, *keys))


def derive_relationship_id(
    config: SimulationRunConfig, *keys: str
) -> RelationshipId:
    """Derive a stable relationship id from seed and canonical keys."""
    return RelationshipId(_derive_purpose_hex(b"relationship", config, *keys))


def derive_memory_id(config: SimulationRunConfig, *keys: str) -> MemoryId:
    """Derive a stable memory id from seed and canonical keys."""
    return MemoryId(_derive_purpose_hex(b"memory", config, *keys))


def derive_belief_id(config: SimulationRunConfig, *keys: str) -> BeliefId:
    """Derive a stable belief id from seed and canonical keys."""
    return BeliefId(_derive_purpose_hex(b"belief", config, *keys))


def derive_envelope_id(config: SimulationRunConfig, *keys: str) -> EnvelopeId:
    """Derive a stable communication envelope id from seed and canonical keys."""
    return EnvelopeId(_derive_purpose_hex(b"envelope", config, *keys))


def reject_operational_identifier(source: str, value: str) -> None:
    """Refuse HTTP/log correlation values as simulation identifiers."""
    raise TypeError(
        f"{source} is operational metadata and cannot populate domain identifiers "
        f"(rejected value length {len(value)})"
    )
