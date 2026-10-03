"""Deterministic namespaced identifiers.

IDs are derived with SHA-256 over canonical bytes. Python's builtin
object hashing is never used. Operational HTTP/log metadata cannot
populate these values.
"""

from __future__ import annotations

import hashlib
import logging

from agents.models import GoalId
from memory.models import BeliefId, MemoryId
from simulation.models import (
    DERIVATION_VERSION_V2,
    DERIVATION_VERSION_V3,
    RunId,
    SimulationRunConfig,
)
from simulation.randomness import StreamScope, canonical_scope_bytes
from social.models import EnvelopeId, RelationshipId
from world.identifiers import (
    EntityId,
    EventId,
    ProposalId,
    RequestId,
    WorldId,
)
from world.models import physical_rules_fingerprint

_LOGGER = logging.getLogger("simulation.identifiers")


def _length_prefixed(value: bytes) -> bytes:
    return len(value).to_bytes(4, "big") + value


def _digest(config: SimulationRunConfig, *parts: bytes) -> bytes:
    hasher = hashlib.sha256()
    assert config.derivation_version is not None
    hasher.update(config.derivation_version.encode("utf-8"))
    if config.derivation_version in {DERIVATION_VERSION_V2, DERIVATION_VERSION_V3}:
        assert config.physical_rules is not None
        fingerprint = physical_rules_fingerprint(config.physical_rules).encode("ascii")
        hasher.update(_length_prefixed(fingerprint))
    if config.derivation_version == DERIVATION_VERSION_V3:
        assert config.stochastic_identity is not None
        identity_bytes = config.stochastic_identity.value.encode("utf-8")
        hasher.update(_length_prefixed(b"stochastic"))
        hasher.update(_length_prefixed(identity_bytes))
    for part in parts:
        hasher.update(_length_prefixed(part))
    return hasher.digest()


def _require_canonical_keys(keys: tuple[str, ...]) -> None:
    if not keys:
        raise ValueError("canonical keys must contain at least one key")
    for key in keys:
        if not isinstance(key, str):
            raise TypeError("canonical keys must be str values")
        if key == "":
            raise ValueError("canonical keys must be non-empty strings")


def _derive_purpose_hex(purpose: bytes, config: SimulationRunConfig, *keys: str) -> str:
    _require_canonical_keys(keys)
    return _digest(
        config,
        purpose,
        str(config.seed).encode("utf-8"),
        *(key.encode("utf-8") for key in keys),
    ).hex()


def derive_run_id(config: SimulationRunConfig) -> RunId:
    """Derive a stable run id from the canonical seed and derivation version."""
    digest = _digest(config, b"run", str(config.seed).encode("utf-8"))
    return RunId(digest.hex())


def derive_scoped_id(config: SimulationRunConfig, scope: StreamScope) -> str:
    """Derive a namespaced id that does not alias distinct scopes."""
    digest = _digest(
        config, b"id", str(config.seed).encode("utf-8"), canonical_scope_bytes(scope)
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


def derive_relationship_id(config: SimulationRunConfig, *keys: str) -> RelationshipId:
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


def derive_system_cause_id(
    config: SimulationRunConfig,
    *,
    run_id: RunId,
    world_id: WorldId,
    tick: int,
    effect_family: str,
    entity_id: EntityId,
    family_ordinal: int,
) -> RequestId:
    """Derive a deterministic system cause/request id for autonomous effects."""
    if type(run_id) is not RunId:
        raise TypeError("derive_system_cause_id requires RunId")
    if type(world_id) is not WorldId:
        raise TypeError("derive_system_cause_id requires WorldId")
    if type(entity_id) is not EntityId:
        raise TypeError("derive_system_cause_id requires EntityId")
    if type(effect_family) is not str or not effect_family:
        raise ValueError("effect_family must be a non-empty str")
    if (
        isinstance(tick, bool)
        or type(tick) is not int
        or tick < 0
        or isinstance(family_ordinal, bool)
        or type(family_ordinal) is not int
        or family_ordinal < 0
    ):
        raise ValueError("tick and family_ordinal must be non-negative ints")
    return derive_request_id(
        config,
        "system-cause",
        run_id.value,
        world_id.value,
        f"tick:{tick}",
        f"family:{effect_family}",
        f"entity:{entity_id.value}",
        f"ordinal:{family_ordinal}",
    )


def _branch_digest(*parts: bytes) -> bytes:
    """SHA-256 over length-prefixed parts under the research-branch namespace."""
    hasher = hashlib.sha256()
    hasher.update(b"research-branch-v1")
    for part in parts:
        hasher.update(_length_prefixed(part))
    return hasher.digest()


def derive_branch_run_id(
    parent_run_id: RunId | str,
    fork_tick: int,
    intervention_fingerprint: str,
    seed_stream_token: str,
) -> RunId:
    """Derive a reproducible child ``run_id`` for a research fork.

    Distinct from seed-only ``derive_run_id``. Alternate seed streams participate
    in the digest only when ``seed_stream_token`` encodes that choice; the
    inherit path must pass the stable inherit token (not a new random stream).
    """
    if type(parent_run_id) is RunId:
        parent_value = parent_run_id.value
    elif isinstance(parent_run_id, str):
        parent_value = parent_run_id
    else:
        raise TypeError("derive_branch_run_id requires RunId or str parent_run_id")
    if isinstance(fork_tick, bool) or type(fork_tick) is not int or fork_tick < 0:
        raise ValueError("fork_tick must be a non-negative int")
    if (
        not isinstance(intervention_fingerprint, str)
        or len(intervention_fingerprint) != 64
    ):
        raise ValueError("intervention_fingerprint must be sha256 hex")
    if not isinstance(seed_stream_token, str) or not seed_stream_token:
        raise ValueError("seed_stream_token must be a non-empty str")
    digest = _branch_digest(
        b"branch-run",
        parent_value.encode("utf-8"),
        str(fork_tick).encode("utf-8"),
        intervention_fingerprint.encode("ascii"),
        seed_stream_token.encode("utf-8"),
    )
    child = RunId(digest.hex())
    _LOGGER.debug(
        "branch_run_id_derived parent_run_id=%s fork_tick=%s child_run_id=%s",
        parent_value,
        fork_tick,
        child.value,
    )
    return child


def derive_branch_id(
    parent_run_id: RunId | str,
    fork_tick: int,
    intervention_fingerprint: str,
    seed_stream_token: str,
) -> str:
    """Derive a stable genealogy ``branch_id`` for a research fork.

    Shares inputs with ``derive_branch_run_id`` but uses a distinct purpose so
    branch ids never collide with child run ids.
    """
    if type(parent_run_id) is RunId:
        parent_value = parent_run_id.value
    elif isinstance(parent_run_id, str):
        parent_value = parent_run_id
    else:
        raise TypeError("derive_branch_id requires RunId or str parent_run_id")
    if isinstance(fork_tick, bool) or type(fork_tick) is not int or fork_tick < 0:
        raise ValueError("fork_tick must be a non-negative int")
    if (
        not isinstance(intervention_fingerprint, str)
        or len(intervention_fingerprint) != 64
    ):
        raise ValueError("intervention_fingerprint must be sha256 hex")
    if not isinstance(seed_stream_token, str) or not seed_stream_token:
        raise ValueError("seed_stream_token must be a non-empty str")
    digest = _branch_digest(
        b"branch-id",
        parent_value.encode("utf-8"),
        str(fork_tick).encode("utf-8"),
        intervention_fingerprint.encode("ascii"),
        seed_stream_token.encode("utf-8"),
    )
    branch_id = digest.hex()
    _LOGGER.debug(
        "branch_id_derived parent_run_id=%s fork_tick=%s branch_id=%s",
        parent_value,
        fork_tick,
        branch_id,
    )
    return branch_id


def reject_operational_identifier(source: str, value: str) -> None:
    """Refuse HTTP/log correlation values as simulation identifiers."""
    raise TypeError(
        f"{source} is operational metadata and cannot populate domain identifiers "
        f"(rejected value length {len(value)})"
    )
