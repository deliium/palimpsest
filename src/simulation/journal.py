"""Canonical persistence codec and commit-hash chain helpers.

Strict UTF-8 JSON with deterministic key ordering. Codecs and hashing are
log-free; errors expose only ``code``, ``path``, and optional ``version``.
Never embed documents, payloads, seeds, or configuration values in messages.

Persistence types are intentionally separate from schema-v1 ``encode_domain``.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any, Final

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.models import RunId, SimulationRunConfig, StochasticIdentity
from simulation.persistence import (
    ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
    PERSISTENCE_CODEC_VERSION,
    CommitHash,
    PayloadHash,
    RunManifest,
    SnapshotId,
    TickCommit,
    WorldSnapshot,
)
from simulation.serialization import (
    DomainSerializationError,
    _decode_agent_body,
    _decode_artifact_content,
    _decode_event_cause,
    _decode_event_details,
    _decode_item,
    _decode_location,
    _decode_physical_rules,
    _decode_resource,
    _decode_weather,
    _encode_agent_body,
    _encode_artifact_content,
    _encode_event_cause,
    _encode_event_details,
    _encode_item,
    _encode_location,
    _encode_physical_rules,
    _encode_resource,
    _encode_weather,
)
from world.repositories import KnowledgeRepository, RepositoryIndexEntry, RepositoryAccessMode, RepositoryStatus
from world.artifacts import (
    ArtifactKind,
    DurableRecordGenre,
    InformationArtifact,
    RecordIntegrity,
)
from world.environment import ActiveHazard, HazardKind
from world.events import (
    EVENT_SCHEMA_REPLAY_V2,
    EVENT_SCHEMA_REPLAY_V3,
    EVENT_SCHEMA_REPLAY_V4,
    EVENT_SCHEMA_REPLAY_V5,
    OccurrenceContext,
    WorldEvent,
    event_is_replayable,
    require_event_details,
    require_replayable_event,
)
from world.identifiers import (
    EntityId,
    EventId,
    RecipeId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.models import PhysicalRules, physical_rules_fingerprint
from world.production import ProductionJob, Structure, StructureKind, ToolMark, ToolRole

_LOGGER: Final[logging.Logger] = logging.getLogger("simulation.journal")

_TYPE_RUN_MANIFEST: Final[str] = "run_manifest"
_TYPE_WORLD_SNAPSHOT: Final[str] = "world_snapshot"
_TYPE_TICK_COMMIT: Final[str] = "tick_commit"
_TYPE_WORLD_EVENT: Final[str] = "world_event"

# Body ids whose assigned_lifespan_ticks were synthesized as a provisional
# placeholder during dual-key decode; restore remaps them to run lifespan.
_PENDING_ASSIGNED_LIFESPAN_SYNTHESIS: set[str] = set()

_TYPE_TAGS: Final[frozenset[str]] = frozenset(
    {
        _TYPE_RUN_MANIFEST,
        _TYPE_WORLD_SNAPSHOT,
        _TYPE_TICK_COMMIT,
        _TYPE_WORLD_EVENT,
    }
)

_EXPECTED_TYPE_MAP: Final[dict[type | str, str]] = {
    RunManifest: _TYPE_RUN_MANIFEST,
    WorldSnapshot: _TYPE_WORLD_SNAPSHOT,
    TickCommit: _TYPE_TICK_COMMIT,
    WorldEvent: _TYPE_WORLD_EVENT,
    _TYPE_RUN_MANIFEST: _TYPE_RUN_MANIFEST,
    _TYPE_WORLD_SNAPSHOT: _TYPE_WORLD_SNAPSHOT,
    _TYPE_TICK_COMMIT: _TYPE_TICK_COMMIT,
    _TYPE_WORLD_EVENT: _TYPE_WORLD_EVENT,
}

__all__ = [
    "PersistenceSerializationError",
    "bind_snapshot_commit_hash",
    "compute_commit_hash",
    "consume_pending_assigned_lifespan_synthesis",
    "decode_persistence",
    "encode_persistence",
    "hash_snapshot",
    "hash_tick_events",
    "hash_tick_payload",
    "hash_world_event",
    "payload_hash",
    "verify_commit_chain",
    "verify_tick_events",
]


def consume_pending_assigned_lifespan_synthesis() -> frozenset[str]:
    """Return and clear body ids needing assigned-lifespan synthesis on restore."""
    pending = frozenset(_PENDING_ASSIGNED_LIFESPAN_SYNTHESIS)
    _PENDING_ASSIGNED_LIFESPAN_SYNTHESIS.clear()
    return pending


class PersistenceSerializationError(ValueError):
    """Fail-closed persistence codec error with stable metadata only."""

    def __init__(self, code: str, path: str, version: str | int | None = None) -> None:
        self.code = code
        self.path = path
        self.version = version
        if version is None:
            super().__init__(f"{code} at {path}")
        else:
            super().__init__(f"{code} at {path} (version={version})")


def encode_persistence(value: object) -> bytes:
    """Encode a supported persistence value to canonical UTF-8 bytes."""
    tag, data = _encode_top(value, path="$")
    envelope = {
        "data": data,
        "persistence_codec_version": PERSISTENCE_CODEC_VERSION,
        "type": tag,
    }
    return _canonical_dumps(envelope)


def decode_persistence(payload: bytes, expected_type: type | str) -> object:
    """Decode canonical persistence bytes into the expected typed value."""
    if expected_type not in _EXPECTED_TYPE_MAP:
        raise PersistenceSerializationError("unsupported_type", "$")
    expected_tag = _EXPECTED_TYPE_MAP[expected_type]
    if not isinstance(payload, (bytes, bytearray)):
        raise PersistenceSerializationError("invalid_bytes", "$")
    if isinstance(payload, bytearray):
        payload = bytes(payload)
    if payload.startswith(b"\xef\xbb\xbf"):
        raise PersistenceSerializationError("bom_forbidden", "$")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PersistenceSerializationError("invalid_utf8", "$") from exc
    decoder = json.JSONDecoder(object_pairs_hook=_reject_duplicate_keys)
    try:
        document, end = decoder.raw_decode(text)
    except PersistenceSerializationError:
        raise
    except json.JSONDecodeError as exc:
        raise PersistenceSerializationError("invalid_json", "$") from exc
    if end != len(text):
        raise PersistenceSerializationError("trailing_data", "$")
    if not isinstance(document, dict):
        raise PersistenceSerializationError("invalid_envelope", "$")
    if set(document) != {"persistence_codec_version", "type", "data"}:
        raise PersistenceSerializationError("invalid_envelope", "$")
    version = document["persistence_codec_version"]
    if (
        not isinstance(version, str)
        or version not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    ):
        raise PersistenceSerializationError(
            "unsupported_version",
            "$.persistence_codec_version",
            version=version if isinstance(version, (str, int)) else None,
        )
    type_tag = document["type"]
    if not isinstance(type_tag, str) or type_tag not in _TYPE_TAGS:
        raise PersistenceSerializationError("invalid_type", "$.type")
    if type_tag != expected_tag:
        raise PersistenceSerializationError("type_mismatch", "$.type")
    data_obj = document["data"]
    if not isinstance(data_obj, dict):
        raise PersistenceSerializationError("invalid_data", "$.data")
    return _decode_top(type_tag, data_obj, path="$.data")


def payload_hash(canonical_bytes: bytes) -> PayloadHash:
    """SHA-256 hex digest of canonical payload bytes."""
    if not isinstance(canonical_bytes, (bytes, bytearray)):
        raise PersistenceSerializationError("invalid_bytes", "$")
    digest = hashlib.sha256(bytes(canonical_bytes)).hexdigest()
    return PayloadHash(digest)


def hash_world_event(event: WorldEvent) -> PayloadHash:
    """Canonical payload hash of one replayable objective event."""
    return payload_hash(encode_persistence(event))


def hash_tick_events(events: Sequence[WorldEvent]) -> tuple[PayloadHash, ...]:
    """Ordered payload hashes for a tick's objective events."""
    if isinstance(events, (set, frozenset, Mapping)):
        raise PersistenceSerializationError("invalid_sequence", "$")
    if isinstance(events, (str, bytes, bytearray)) or not isinstance(events, Sequence):
        raise PersistenceSerializationError("invalid_sequence", "$")
    return tuple(hash_world_event(event) for event in events)


def hash_tick_payload(events: Sequence[WorldEvent]) -> PayloadHash:
    """Canonical tick payload hash from ordered objective event hashes."""
    event_hashes = hash_tick_events(events)
    document = {"event_hashes": [item.value for item in event_hashes]}
    return payload_hash(_canonical_dumps(document))


def compute_commit_hash(
    *,
    predecessor_commit_hash: CommitHash | None,
    run_id: RunId,
    tick: Tick,
    base_revision: WorldRevision,
    resulting_revision: WorldRevision,
    event_hashes: Sequence[PayloadHash],
    payload_hash: PayloadHash,
) -> CommitHash:
    """Derive the chained per-run commit digest from cursor and event hashes."""
    tick_payload_hash = payload_hash
    if type(run_id) is not RunId:
        raise PersistenceSerializationError("invalid_type", "$.run_id")
    if type(tick) is not Tick:
        raise PersistenceSerializationError("invalid_type", "$.tick")
    if type(base_revision) is not WorldRevision:
        raise PersistenceSerializationError("invalid_type", "$.base_revision")
    if type(resulting_revision) is not WorldRevision:
        raise PersistenceSerializationError("invalid_type", "$.resulting_revision")
    if predecessor_commit_hash is not None and type(predecessor_commit_hash) is not (
        CommitHash
    ):
        raise PersistenceSerializationError("invalid_type", "$.predecessor_commit_hash")
    if type(tick_payload_hash) is not PayloadHash:
        raise PersistenceSerializationError("invalid_type", "$.payload_hash")
    if isinstance(event_hashes, (set, frozenset, Mapping)):
        raise PersistenceSerializationError("invalid_sequence", "$.event_hashes")
    if isinstance(event_hashes, (str, bytes, bytearray)) or not isinstance(
        event_hashes, Sequence
    ):
        raise PersistenceSerializationError("invalid_sequence", "$.event_hashes")
    ordered_hashes: list[str] = []
    for index, item in enumerate(event_hashes):
        if type(item) is not PayloadHash:
            raise PersistenceSerializationError(
                "invalid_type", f"$.event_hashes[{index}]"
            )
        ordered_hashes.append(item.value)
    document = {
        "base_revision": base_revision.value,
        "event_hashes": ordered_hashes,
        "payload_hash": tick_payload_hash.value,
        "predecessor_commit_hash": (
            None if predecessor_commit_hash is None else predecessor_commit_hash.value
        ),
        "resulting_revision": resulting_revision.value,
        "run_id": run_id.value,
        "tick": tick.value,
    }
    digest = hashlib.sha256(_canonical_dumps(document)).hexdigest()
    return CommitHash(digest)


def verify_commit_chain(commits: Sequence[TickCommit]) -> None:
    """Validate contiguous ticks and predecessor commit-hash links.

    Raises ``PersistenceSerializationError`` with a stable code on gap or
    predecessor mismatch. Does not re-hash event payloads (those are checked
    when commits are produced).
    """
    if isinstance(commits, (set, frozenset, Mapping)):
        raise PersistenceSerializationError("invalid_sequence", "$")
    if isinstance(commits, (str, bytes, bytearray)) or not isinstance(
        commits, Sequence
    ):
        raise PersistenceSerializationError("invalid_sequence", "$")
    previous: TickCommit | None = None
    for index, commit in enumerate(commits):
        path = f"$[{index}]"
        if type(commit) is not TickCommit:
            raise PersistenceSerializationError("invalid_type", path)
        if previous is not None:
            if commit.run_id != previous.run_id:
                raise PersistenceSerializationError("run_id_mismatch", f"{path}.run_id")
            if commit.tick.value != previous.tick.value + 1:
                raise PersistenceSerializationError("commit_chain_gap", f"{path}.tick")
            if commit.predecessor_commit_hash != previous.commit_hash:
                raise PersistenceSerializationError(
                    "predecessor_mismatch", f"{path}.predecessor_commit_hash"
                )
        previous = commit


def verify_tick_events(
    events: Sequence[WorldEvent],
    *,
    expected_payload_hash: PayloadHash | None = None,
    expected_event_hashes: Sequence[PayloadHash] | None = None,
) -> None:
    """Verify replayable event identity, ordering, and optional hash layers."""
    if isinstance(events, (set, frozenset, Mapping)):
        raise PersistenceSerializationError("invalid_sequence", "$")
    if isinstance(events, (str, bytes, bytearray)) or not isinstance(events, Sequence):
        raise PersistenceSerializationError("invalid_sequence", "$")
    schema_version: int | None = None
    prior_tick: int | None = None
    prior_sequence: int | None = None
    for index, event in enumerate(events):
        path = f"$[{index}]"
        if type(event) is not WorldEvent:
            raise PersistenceSerializationError("invalid_type", path)
        try:
            require_replayable_event(event)
        except (TypeError, ValueError) as exc:
            raise PersistenceSerializationError("non_replayable_event", path) from exc
        if event.schema_version not in {
            EVENT_SCHEMA_REPLAY_V2,
            EVENT_SCHEMA_REPLAY_V3,
            EVENT_SCHEMA_REPLAY_V4,
            EVENT_SCHEMA_REPLAY_V5,
        }:
            raise PersistenceSerializationError(
                "unsupported_version",
                f"{path}.schema_version",
                version=event.schema_version,
            )
        if schema_version is None:
            schema_version = event.schema_version
        elif event.schema_version != schema_version:
            raise PersistenceSerializationError(
                "mixed_schema_version", f"{path}.schema_version"
            )
        if prior_tick is None:
            prior_tick = event.tick
            prior_sequence = event.sequence
            if event.sequence != 0:
                raise PersistenceSerializationError("sequence_gap", f"{path}.sequence")
        elif event.tick == prior_tick:
            if prior_sequence is None or event.sequence != prior_sequence + 1:
                raise PersistenceSerializationError("sequence_gap", f"{path}.sequence")
            prior_sequence = event.sequence
        elif event.tick < prior_tick:
            raise PersistenceSerializationError("invalid_ordering", f"{path}.tick")
        else:
            if event.sequence != 0:
                raise PersistenceSerializationError("sequence_gap", f"{path}.sequence")
            prior_tick = event.tick
            prior_sequence = event.sequence
        recomputed = hash_world_event(event)
        if expected_event_hashes is not None:
            if index >= len(expected_event_hashes):
                raise PersistenceSerializationError("hash_mismatch", path)
            if recomputed != expected_event_hashes[index]:
                raise PersistenceSerializationError("hash_mismatch", path)
    if expected_event_hashes is not None and len(expected_event_hashes) != len(events):
        raise PersistenceSerializationError("hash_mismatch", "$")
    if expected_payload_hash is not None:
        if hash_tick_payload(events) != expected_payload_hash:
            raise PersistenceSerializationError("hash_mismatch", "$.payload_hash")


def hash_snapshot(snapshot: WorldSnapshot) -> PayloadHash:
    """Integrity hash of a snapshot excluding the ``integrity_hash`` field."""
    if type(snapshot) is not WorldSnapshot:
        raise PersistenceSerializationError("invalid_type", "$")
    body = _encode_world_snapshot(snapshot, include_integrity_hash=False)
    return payload_hash(_canonical_dumps(body))


def bind_snapshot_commit_hash(
    snapshot: WorldSnapshot, commit_hash: CommitHash
) -> WorldSnapshot:
    """Bind a checkpoint to the tick commit that produced it and rehash.

    ``WorldSnapshot.predecessor_commit_hash`` is the chain cursor after the
    producing tick so the next tick's predecessor matches on replay.
    """
    if type(snapshot) is not WorldSnapshot:
        raise PersistenceSerializationError("invalid_type", "$")
    if type(commit_hash) is not CommitHash:
        raise PersistenceSerializationError("invalid_type", "$.commit_hash")
    draft = WorldSnapshot(
        snapshot_id=snapshot.snapshot_id,
        run_id=snapshot.run_id,
        world_id=snapshot.world_id,
        seed=snapshot.seed,
        config=snapshot.config,
        registrations=snapshot.registrations,
        locations=snapshot.locations,
        bodies=snapshot.bodies,
        items=snapshot.items,
        resources=snapshot.resources,
        weather=snapshot.weather,
        next_tick=snapshot.next_tick,
        revision=snapshot.revision,
        event_schema_version=snapshot.event_schema_version,
        projector_version=snapshot.projector_version,
        persistence_codec_version=snapshot.persistence_codec_version,
        derivation_version=snapshot.derivation_version,
        integrity_hash=snapshot.integrity_hash,
        predecessor_commit_hash=commit_hash,
        structures=snapshot.structures,
        production_jobs=snapshot.production_jobs,
        tool_marks=snapshot.tool_marks,
        active_hazards=snapshot.active_hazards,
        artifacts=snapshot.artifacts,
        lifecycle_records=snapshot.lifecycle_records,
        kinship_edges=snapshot.kinship_edges,
        dependency_need_registers=snapshot.dependency_need_registers,
        repositories=snapshot.repositories,
    )
    return WorldSnapshot(
        snapshot_id=draft.snapshot_id,
        run_id=draft.run_id,
        world_id=draft.world_id,
        seed=draft.seed,
        config=draft.config,
        registrations=draft.registrations,
        locations=draft.locations,
        bodies=draft.bodies,
        items=draft.items,
        resources=draft.resources,
        weather=draft.weather,
        next_tick=draft.next_tick,
        revision=draft.revision,
        event_schema_version=draft.event_schema_version,
        projector_version=draft.projector_version,
        persistence_codec_version=draft.persistence_codec_version,
        derivation_version=draft.derivation_version,
        integrity_hash=hash_snapshot(draft),
        predecessor_commit_hash=commit_hash,
        structures=draft.structures,
        production_jobs=draft.production_jobs,
        tool_marks=draft.tool_marks,
        active_hazards=draft.active_hazards,
        artifacts=draft.artifacts,
        lifecycle_records=draft.lifecycle_records,
        kinship_edges=draft.kinship_edges,
        dependency_need_registers=draft.dependency_need_registers,
        repositories=draft.repositories,
    )


def _canonical_dumps(value: object) -> bytes:
    text = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return text.encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PersistenceSerializationError("duplicate_key", "$")
        result[key] = value
    return result


def _map_domain_error(exc: DomainSerializationError) -> PersistenceSerializationError:
    code = exc.code
    if code == "non_finite_float":
        code = "non_finite_number"
    elif code == "invalid_model":
        code = "malformed_id"
    return PersistenceSerializationError(code, exc.path)


def _encode_top(value: object, *, path: str) -> tuple[str, dict[str, Any]]:
    if type(value) is RunManifest:
        return _TYPE_RUN_MANIFEST, _encode_run_manifest(value)
    if type(value) is WorldSnapshot:
        return _TYPE_WORLD_SNAPSHOT, _encode_world_snapshot(
            value, include_integrity_hash=True
        )
    if type(value) is TickCommit:
        return _TYPE_TICK_COMMIT, _encode_tick_commit(value)
    if type(value) is WorldEvent:
        return _TYPE_WORLD_EVENT, _encode_world_event(value, path=path)
    raise PersistenceSerializationError("unsupported_type", path)


def _decode_top(tag: str, data: dict[str, Any], *, path: str) -> object:
    if tag == _TYPE_RUN_MANIFEST:
        return _decode_run_manifest(data, path=path)
    if tag == _TYPE_WORLD_SNAPSHOT:
        return _decode_world_snapshot(data, path=path)
    if tag == _TYPE_TICK_COMMIT:
        return _decode_tick_commit(data, path=path)
    if tag == _TYPE_WORLD_EVENT:
        return _decode_world_event(data, path=path)
    raise PersistenceSerializationError("invalid_type", "$.type")


def _require_keys(data: Mapping[str, Any], keys: set[str], *, path: str) -> None:
    actual = set(data)
    if actual != keys:
        if actual - keys:
            raise PersistenceSerializationError("unknown_field", path)
        raise PersistenceSerializationError("invalid_fields", path)


def _str_field(data: Mapping[str, Any], key: str, *, path: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise PersistenceSerializationError("invalid_string", f"{path}.{key}")
    return value


def _nonneg_int_field(data: Mapping[str, Any], key: str, *, path: str) -> int:
    """Exact non-negative int with no 64-bit upper bound (seeds, ticks, etc.)."""
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise PersistenceSerializationError("invalid_int", f"{path}.{key}")
    if value < 0:
        raise PersistenceSerializationError("invalid_int", f"{path}.{key}")
    return value


def _float_field(data: Mapping[str, Any], key: str, *, path: str) -> float:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PersistenceSerializationError("non_finite_float", f"{path}.{key}")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise PersistenceSerializationError("non_finite_float", f"{path}.{key}")
    return number


def _encode_seed(seed: int) -> int:
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise PersistenceSerializationError("invalid_int", "$.seed")
    return seed


def _encode_run_manifest(value: RunManifest) -> dict[str, Any]:
    return {
        "config": _encode_config(value.config),
        "derivation_version": value.derivation_version,
        "event_schema_version": value.event_schema_version,
        "persistence_codec_version": value.persistence_codec_version,
        "projector_version": value.projector_version,
        "run_id": value.run_id.value,
        "seed": _encode_seed(value.seed),
        "world_id": value.world_id.value,
    }


def _decode_run_manifest(data: dict[str, Any], *, path: str) -> RunManifest:
    _require_keys(
        data,
        {
            "run_id",
            "world_id",
            "seed",
            "config",
            "derivation_version",
            "event_schema_version",
            "projector_version",
            "persistence_codec_version",
        },
        path=path,
    )
    config_raw = data["config"]
    if not isinstance(config_raw, dict):
        raise PersistenceSerializationError("invalid_object", f"{path}.config")
    try:
        return RunManifest(
            run_id=RunId(_str_field(data, "run_id", path=path)),
            world_id=WorldId(_str_field(data, "world_id", path=path)),
            seed=_nonneg_int_field(data, "seed", path=path),
            config=_decode_config(config_raw, path=f"{path}.config"),
            derivation_version=_str_field(data, "derivation_version", path=path),
            event_schema_version=_nonneg_int_field(
                data, "event_schema_version", path=path
            ),
            projector_version=_str_field(data, "projector_version", path=path),
            persistence_codec_version=_str_field(
                data, "persistence_codec_version", path=path
            ),
        )
    except PersistenceSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise PersistenceSerializationError("malformed_id", path) from exc


def _encode_config(config: SimulationRunConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {"seed": _encode_seed(config.seed)}
    if config.physical_rules is not None:
        try:
            payload["physical_rules"] = _encode_physical_rules(config.physical_rules)
        except DomainSerializationError as exc:
            raise _map_domain_error(exc) from exc
        payload["derivation_version"] = config.derivation_version
        payload["rules_fingerprint"] = physical_rules_fingerprint(config.physical_rules)
    if config.stochastic_identity is not None:
        payload["derivation_version"] = config.derivation_version
        payload["stochastic_identity"] = config.stochastic_identity.value
    return payload


def _decode_config(data: dict[str, Any], *, path: str) -> SimulationRunConfig:
    keys = set(data)
    if keys == {"seed"}:
        try:
            return SimulationRunConfig(seed=_nonneg_int_field(data, "seed", path=path))
        except PersistenceSerializationError:
            raise
        except (TypeError, ValueError) as exc:
            raise PersistenceSerializationError("invalid_model", path) from exc
    allowed = {
        "seed",
        "physical_rules",
        "derivation_version",
        "rules_fingerprint",
        "stochastic_identity",
    }
    if keys - allowed or "seed" not in keys:
        raise PersistenceSerializationError("invalid_fields", path)
    rules: PhysicalRules | None = None
    if "physical_rules" in data:
        rules_raw = data["physical_rules"]
        if not isinstance(rules_raw, dict):
            raise PersistenceSerializationError(
                "invalid_object", f"{path}.physical_rules"
            )
        try:
            rules = _decode_physical_rules(rules_raw, path=f"{path}.physical_rules")
        except DomainSerializationError as exc:
            raise _map_domain_error(exc) from exc
        if "rules_fingerprint" in data:
            expected = _str_field(data, "rules_fingerprint", path=path)
            actual = physical_rules_fingerprint(rules)
            if actual != expected:
                raise PersistenceSerializationError(
                    "hash_mismatch", f"{path}.rules_fingerprint"
                )
    derivation = (
        _str_field(data, "derivation_version", path=path)
        if "derivation_version" in data
        else None
    )
    stochastic = None
    if "stochastic_identity" in data:
        try:
            stochastic = StochasticIdentity(
                _str_field(data, "stochastic_identity", path=path)
            )
        except (TypeError, ValueError) as exc:
            raise PersistenceSerializationError(
                "invalid_model", f"{path}.stochastic_identity"
            ) from exc
    try:
        return SimulationRunConfig(
            seed=_nonneg_int_field(data, "seed", path=path),
            physical_rules=rules,
            derivation_version=derivation,
            stochastic_identity=stochastic,
        )
    except PersistenceSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        code = "invalid_model"
        message = str(exc)
        if "stochastic_identity_absent" in message:
            code = "stochastic_identity_absent"
        elif "stochastic_identity_mismatch" in message:
            code = "stochastic_identity_mismatch"
        raise PersistenceSerializationError(code, path) from exc


def _encode_registration(value: AgentRegistration) -> dict[str, Any]:
    return {
        "agent_id": value.agent_id.value,
        "entity_id": value.entity_id.value,
    }


def _decode_registration(data: dict[str, Any], *, path: str) -> AgentRegistration:
    _require_keys(data, {"agent_id", "entity_id"}, path=path)
    try:
        return AgentRegistration(
            agent_id=AgentId(_str_field(data, "agent_id", path=path)),
            entity_id=EntityId(_str_field(data, "entity_id", path=path)),
        )
    except PersistenceSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise PersistenceSerializationError("malformed_id", path) from exc


def _encode_world_snapshot(
    value: WorldSnapshot, *, include_integrity_hash: bool
) -> dict[str, Any]:
    try:
        payload: dict[str, Any] = {
            "bodies": [_encode_agent_body(body) for body in value.bodies],
            "config": _encode_config(value.config),
            "derivation_version": value.derivation_version,
            "event_schema_version": value.event_schema_version,
            "items": [_encode_item(item) for item in value.items],
            "locations": [_encode_location(loc) for loc in value.locations],
            "next_tick": value.next_tick.value,
            "persistence_codec_version": value.persistence_codec_version,
            "predecessor_commit_hash": (
                None
                if value.predecessor_commit_hash is None
                else value.predecessor_commit_hash.value
            ),
            "projector_version": value.projector_version,
            "registrations": [_encode_registration(reg) for reg in value.registrations],
            "resources": [_encode_resource(item) for item in value.resources],
            "revision": value.revision.value,
            "run_id": value.run_id.value,
            "seed": _encode_seed(value.seed),
            "snapshot_id": value.snapshot_id.value,
            "weather": [_encode_weather(item) for item in value.weather],
            "world_id": value.world_id.value,
        }
        if value.persistence_codec_version in {"v3", "v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11",
            "v12",
        }:
            payload["structures"] = [
                _encode_structure(item) for item in value.structures
            ]
            payload["production_jobs"] = [
                _encode_production_job(item) for item in value.production_jobs
            ]
            payload["tool_marks"] = [
                _encode_tool_mark(item) for item in value.tool_marks
            ]
        if value.persistence_codec_version in {"v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11",
            "v12",
        }:
            payload["active_hazards"] = [
                _encode_active_hazard(item) for item in value.active_hazards
            ]
        if value.persistence_codec_version in {"v5", "v6", "v7", "v8", "v9", "v10", "v11",
            "v12",
        }:
            payload["artifacts"] = [
                _encode_information_artifact(item) for item in value.artifacts
            ]
        if value.persistence_codec_version in {"v6", "v7", "v8", "v9", "v10", "v11",
            "v12",
        }:
            payload["lifecycle_records"] = [
                _encode_lifecycle_record(item) for item in value.lifecycle_records
            ]
        if value.persistence_codec_version in {"v8", "v9", "v10", "v11", "v12"}:
            payload["kinship_edges"] = [
                _encode_kinship_edge(item) for item in value.kinship_edges
            ]
        if value.persistence_codec_version in {"v9", "v10", "v11", "v12"}:
            payload["dependency_need_registers"] = [
                _encode_dependency_need_register(item)
                for item in value.dependency_need_registers
            ]
        if value.persistence_codec_version in {"v11", "v12"}:
            payload["repositories"] = [
                _encode_knowledge_repository(item) for item in value.repositories
            ]
            custody = sum(
                1
                for item in value.artifacts
                if item.custodian_repository_id is not None
            )
            _LOGGER.debug(
                "repository_snapshot_encode repository_count=%s custody_count=%s",
                len(value.repositories),
                custody,
            )
    except DomainSerializationError as exc:
        raise _map_domain_error(exc) from exc
    if include_integrity_hash:
        payload["integrity_hash"] = value.integrity_hash.value
    return payload


def _decode_world_snapshot(data: dict[str, Any], *, path: str) -> WorldSnapshot:
    codec = data.get("persistence_codec_version")
    keys = {
        "snapshot_id",
        "run_id",
        "world_id",
        "seed",
        "config",
        "registrations",
        "locations",
        "bodies",
        "items",
        "resources",
        "weather",
        "next_tick",
        "revision",
        "event_schema_version",
        "projector_version",
        "persistence_codec_version",
        "derivation_version",
        "integrity_hash",
        "predecessor_commit_hash",
    }
    if codec in {"v3", "v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11", "v12"}:
        keys |= {"structures", "production_jobs", "tool_marks"}
    if codec in {"v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11", "v12"}:
        keys.add("active_hazards")
    if codec in {"v5", "v6", "v7", "v8", "v9", "v10", "v11", "v12"}:
        keys.add("artifacts")
    if codec in {"v6", "v7", "v8", "v9", "v10", "v11", "v12"}:
        keys.add("lifecycle_records")
    if codec in {"v8", "v9", "v10", "v11", "v12"}:
        keys.add("kinship_edges")
    if codec in {"v9", "v10", "v11", "v12"}:
        keys.add("dependency_need_registers")
    if codec in {"v11", "v12"}:
        keys.add("repositories")
    _require_keys(data, keys, path=path)
    config_raw = data["config"]
    if not isinstance(config_raw, dict):
        raise PersistenceSerializationError("invalid_object", f"{path}.config")
    try:
        predecessor_raw = data["predecessor_commit_hash"]
        predecessor: CommitHash | None
        if predecessor_raw is None:
            predecessor = None
        elif isinstance(predecessor_raw, str):
            predecessor = CommitHash(predecessor_raw)
        else:
            raise PersistenceSerializationError(
                "invalid_string", f"{path}.predecessor_commit_hash"
            )
        snapshot = WorldSnapshot(
            snapshot_id=SnapshotId(_str_field(data, "snapshot_id", path=path)),
            run_id=RunId(_str_field(data, "run_id", path=path)),
            world_id=WorldId(_str_field(data, "world_id", path=path)),
            seed=_nonneg_int_field(data, "seed", path=path),
            config=_decode_config(config_raw, path=f"{path}.config"),
            registrations=_decode_object_list(
                data["registrations"],
                _decode_registration,
                path=f"{path}.registrations",
            ),
            locations=_decode_domain_object_list(
                data["locations"], _decode_location, path=f"{path}.locations"
            ),
            bodies=_decode_domain_object_list(
                data["bodies"], _decode_agent_body, path=f"{path}.bodies"
            ),
            items=_decode_domain_object_list(
                data["items"], _decode_item, path=f"{path}.items"
            ),
            resources=_decode_domain_object_list(
                data["resources"], _decode_resource, path=f"{path}.resources"
            ),
            weather=_decode_domain_object_list(
                data["weather"], _decode_weather, path=f"{path}.weather"
            ),
            next_tick=Tick(_nonneg_int_field(data, "next_tick", path=path)),
            revision=WorldRevision(_nonneg_int_field(data, "revision", path=path)),
            event_schema_version=_nonneg_int_field(
                data, "event_schema_version", path=path
            ),
            projector_version=_str_field(data, "projector_version", path=path),
            persistence_codec_version=_str_field(
                data, "persistence_codec_version", path=path
            ),
            derivation_version=_str_field(data, "derivation_version", path=path),
            integrity_hash=PayloadHash(_str_field(data, "integrity_hash", path=path)),
            predecessor_commit_hash=predecessor,
            structures=_decode_object_list(
                data["structures"], _decode_structure, path=f"{path}.structures"
            )
            if codec in {"v3", "v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11", "v12"}
            else (),
            production_jobs=_decode_object_list(
                data["production_jobs"],
                _decode_production_job,
                path=f"{path}.production_jobs",
            )
            if codec in {"v3", "v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11", "v12"}
            else (),
            tool_marks=_decode_object_list(
                data["tool_marks"], _decode_tool_mark, path=f"{path}.tool_marks"
            )
            if codec in {"v3", "v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11", "v12"}
            else (),
            active_hazards=_decode_object_list(
                data["active_hazards"],
                _decode_active_hazard,
                path=f"{path}.active_hazards",
            )
            if codec in {"v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11", "v12"}
            else (),
            artifacts=_decode_object_list(
                data["artifacts"],
                _decode_information_artifact,
                path=f"{path}.artifacts",
            )
            if codec in {"v5", "v6", "v7", "v8", "v9", "v10", "v11", "v12"}
            else (),
            lifecycle_records=_decode_object_list(
                data["lifecycle_records"],
                _decode_lifecycle_record,
                path=f"{path}.lifecycle_records",
            )
            if codec in {"v6", "v7", "v8", "v9", "v10", "v11", "v12"}
            else (),
            kinship_edges=_decode_object_list(
                data["kinship_edges"],
                _decode_kinship_edge,
                path=f"{path}.kinship_edges",
            )
            if codec in {"v8", "v9", "v10", "v11", "v12"}
            else (),
            dependency_need_registers=_decode_object_list(
                data["dependency_need_registers"],
                _decode_dependency_need_register,
                path=f"{path}.dependency_need_registers",
            )
            if codec in {"v9", "v10", "v11", "v12"}
            else (),
            repositories=_decode_object_list(
                data["repositories"],
                _decode_knowledge_repository,
                path=f"{path}.repositories",
            )
            if codec in {"v11", "v12"}
            else (),
        )
    except PersistenceSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise PersistenceSerializationError("malformed_id", path) from exc
    # Dual-key ≤v10 synthesizes empty repositories; v11 logs custody counts.
    if codec in {"v11", "v12"}:
        custody = sum(
            1
            for item in snapshot.artifacts
            if item.custodian_repository_id is not None
        )
        _LOGGER.debug(
            "repository_snapshot_decode repository_count=%s custody_count=%s",
            len(snapshot.repositories),
            custody,
        )
    else:
        _LOGGER.debug(
            "repository_snapshot_decode repository_count=0 "
            "custody_count=0 synthesized_empty=true",
        )
    return snapshot


_LIFECYCLE_RECORD_KEYS_BASE: Final[frozenset[str]] = frozenset(
    {
        "agent_id",
        "body_id",
        "cohort_id",
        "dependency_status",
        "entry_tick",
        "generation_index",
        "provenance",
        "stage",
    }
)
_LIFECYCLE_RECORD_KEYS_WITH_ASSIGNED: Final[frozenset[str]] = (
    _LIFECYCLE_RECORD_KEYS_BASE | frozenset({"assigned_lifespan_ticks"})
)


def _encode_kinship_edge(value: object) -> dict[str, Any]:
    from world.kinship import KinshipEdge

    if type(value) is not KinshipEdge:
        raise TypeError("kinship_edges entries must be KinshipEdge")
    return {
        "child_agent_id": value.child_agent_id.value,
        "edge_id": value.edge_id,
        "established_tick": value.established_tick,
        "parent_agent_id": value.parent_agent_id.value,
    }


def _encode_dependency_need_register(value: object) -> dict[str, Any]:
    from world.dependency_care import DependencyNeedRegister

    if type(value) is not DependencyNeedRegister:
        raise TypeError(
            "dependency_need_registers entries must be DependencyNeedRegister"
        )
    return {
        "agent_id": value.agent_id.value,
        "deficits": dict(value.deficits),
    }


def _decode_kinship_edge(data: dict[str, Any], *, path: str) -> object:
    from agents.models import AgentId
    from world.kinship import KinshipEdge, stable_kinship_edge_id

    _require_keys(
        data,
        {
            "parent_agent_id",
            "child_agent_id",
            "established_tick",
            "edge_id",
        },
        path=path,
    )
    parent = AgentId(_str_field(data, "parent_agent_id", path=path))
    child = AgentId(_str_field(data, "child_agent_id", path=path))
    tick = _nonneg_int_field(data, "established_tick", path=path)
    edge_id = _str_field(data, "edge_id", path=path)
    expected = stable_kinship_edge_id(
        parent_agent_id=parent,
        child_agent_id=child,
        established_tick=tick,
    )
    if edge_id != expected:
        raise PersistenceSerializationError("invalid_string", f"{path}.edge_id")
    return KinshipEdge(
        parent_agent_id=parent,
        child_agent_id=child,
        established_tick=tick,
        edge_id=expected,
    )


def _decode_dependency_need_register(data: dict[str, Any], *, path: str) -> object:
    from agents.models import AgentId
    from world.dependency_care import DependencyNeedRegister

    _require_keys(data, {"agent_id", "deficits"}, path=path)
    agent_id = AgentId(_str_field(data, "agent_id", path=path))
    deficits_raw = data["deficits"]
    if not isinstance(deficits_raw, Mapping):
        raise PersistenceSerializationError("invalid_object", f"{path}.deficits")
    deficits: dict[str, float] = {}
    for key, value in deficits_raw.items():
        if type(key) is not str:
            raise PersistenceSerializationError(
                "invalid_string", f"{path}.deficits.key"
            )
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PersistenceSerializationError(
                "invalid_number", f"{path}.deficits.{key}"
            )
        deficits[key] = float(value)
    return DependencyNeedRegister(agent_id=agent_id, deficits=deficits)


def _encode_lifecycle_record(value: object) -> dict[str, Any]:
    from world.lifecycle import AgentLifecycleRecord

    if type(value) is not AgentLifecycleRecord:
        raise TypeError("lifecycle_records entries must be AgentLifecycleRecord")
    return {
        "agent_id": value.agent_id,
        "assigned_lifespan_ticks": value.assigned_lifespan_ticks,
        "body_id": value.body_id.value,
        "cohort_id": value.cohort_id,
        "dependency_status": value.dependency_status.value,
        "entry_tick": value.entry_tick,
        "generation_index": value.generation_index,
        "provenance": value.provenance.value,
        "stage": value.stage.value,
    }


def _decode_lifecycle_record(data: dict[str, Any], *, path: str) -> object:
    from world.lifecycle import (
        AgentLifecycleRecord,
        DependencyStatus,
        LifecycleStageId,
        OriginProvenance,
    )

    actual = frozenset(data.keys())
    if actual == _LIFECYCLE_RECORD_KEYS_WITH_ASSIGNED:
        has_assigned = True
    elif actual == _LIFECYCLE_RECORD_KEYS_BASE:
        has_assigned = False
    else:
        _LOGGER.error(
            "lifecycle_record_key_set_invalid path=%s actual=%s",
            path,
            sorted(actual),
        )
        raise PersistenceSerializationError("unexpected_keys", path)
    try:
        body_id = _str_field(data, "body_id", path=path)
        if has_assigned:
            raw_assigned = data["assigned_lifespan_ticks"]
            if (
                isinstance(raw_assigned, bool)
                or type(raw_assigned) is not int
                or raw_assigned < 1
            ):
                raise PersistenceSerializationError(
                    "invalid_int", f"{path}.assigned_lifespan_ticks"
                )
            assigned = raw_assigned
            _LOGGER.debug(
                "lifecycle_record_decode path=%s has_assigned_lifespan=true "
                "synthesized=false",
                path,
            )
        else:
            # Provisional placeholder; restore remaps via pending synthesis set
            # to run-level lifespan_ticks (fixed equivalence).
            assigned = 1
            _PENDING_ASSIGNED_LIFESPAN_SYNTHESIS.add(body_id)
            _LOGGER.debug(
                "lifecycle_record_decode path=%s has_assigned_lifespan=false "
                "synthesized=pending body_id=%s",
                path,
                body_id,
            )
        return AgentLifecycleRecord(
            body_id=EntityId(body_id),
            agent_id=_str_field(data, "agent_id", path=path),
            entry_tick=_nonneg_int_field(data, "entry_tick", path=path),
            stage=LifecycleStageId(_str_field(data, "stage", path=path)),
            dependency_status=DependencyStatus(
                _str_field(data, "dependency_status", path=path)
            ),
            generation_index=_nonneg_int_field(data, "generation_index", path=path),
            cohort_id=_str_field(data, "cohort_id", path=path),
            provenance=OriginProvenance(_str_field(data, "provenance", path=path)),
            assigned_lifespan_ticks=assigned,
        )
    except (TypeError, ValueError) as exc:
        raise PersistenceSerializationError("invalid_model", path) from exc


_DURABLE_ARTIFACT_KEYS: frozenset[str] = frozenset(
    {
        "record_genre",
        "parent_artifact_id",
        "source_artifact_id",
        "copy_generation",
        "integrity",
        "annotation_revisions",
        "lost_mark_count",
        "custodian_repository_id",
    }
)


def _encode_information_artifact(value: InformationArtifact) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "artifact_id": value.artifact_id.value,
        "author_id": value.author_id.value,
        "content": _encode_artifact_content(value.content),
        "content_revision": value.content_revision,
        "created_tick": value.created_tick,
        "kind": value.kind.value,
    }
    if value.location_id is not None:
        payload["location_id"] = value.location_id.value
    if value.holder_id is not None:
        payload["holder_id"] = value.holder_id.value
    # Codec v10 additive durable fields; omitted when all defaults (v9 decode OK).
    if value.record_genre is not None:
        payload["record_genre"] = value.record_genre.value
    if value.parent_artifact_id is not None:
        payload["parent_artifact_id"] = value.parent_artifact_id.value
    if value.source_artifact_id is not None:
        payload["source_artifact_id"] = value.source_artifact_id.value
    if value.copy_generation:
        payload["copy_generation"] = value.copy_generation
    if value.integrity is not RecordIntegrity.INTACT:
        payload["integrity"] = value.integrity.value
    if value.annotation_revisions:
        payload["annotation_revisions"] = value.annotation_revisions
    if value.lost_mark_count:
        payload["lost_mark_count"] = value.lost_mark_count
    if value.custodian_repository_id is not None:
        payload["custodian_repository_id"] = value.custodian_repository_id.value
    return payload


def _decode_information_artifact(
    data: dict[str, Any], *, path: str
) -> InformationArtifact:
    base = {
        "artifact_id",
        "kind",
        "author_id",
        "created_tick",
        "content",
        "content_revision",
    }
    allowed = base | {"location_id", "holder_id"} | _DURABLE_ARTIFACT_KEYS
    if set(data) - allowed or not base.issubset(data):
        raise PersistenceSerializationError("invalid_fields", path)
    location_raw = data.get("location_id")
    holder_raw = data.get("holder_id")
    location_id: EntityId | None
    holder_id: EntityId | None
    if location_raw is None:
        location_id = None
    elif isinstance(location_raw, str):
        location_id = EntityId(location_raw)
    else:
        raise PersistenceSerializationError("invalid_string", f"{path}.location_id")
    if holder_raw is None:
        holder_id = None
    elif isinstance(holder_raw, str):
        holder_id = EntityId(holder_raw)
    else:
        raise PersistenceSerializationError("invalid_string", f"{path}.holder_id")

    genre_raw = data.get("record_genre")
    record_genre: DurableRecordGenre | None
    if genre_raw is None:
        record_genre = None
    elif isinstance(genre_raw, str):
        try:
            record_genre = DurableRecordGenre(genre_raw)
        except ValueError as exc:
            raise PersistenceSerializationError(
                "invalid_string", f"{path}.record_genre"
            ) from exc
    else:
        raise PersistenceSerializationError("invalid_string", f"{path}.record_genre")

    def _optional_entity(key: str) -> EntityId | None:
        raw = data.get(key)
        if raw is None:
            return None
        if isinstance(raw, str):
            return EntityId(raw)
        raise PersistenceSerializationError("invalid_string", f"{path}.{key}")

    parent_artifact_id = _optional_entity("parent_artifact_id")
    source_artifact_id = _optional_entity("source_artifact_id")
    copy_generation = int(data.get("copy_generation", 0))
    integrity_raw = data.get("integrity")
    if integrity_raw is None:
        integrity = RecordIntegrity.INTACT
    elif isinstance(integrity_raw, str):
        try:
            integrity = RecordIntegrity(integrity_raw)
        except ValueError as exc:
            raise PersistenceSerializationError(
                "invalid_string", f"{path}.integrity"
            ) from exc
    else:
        raise PersistenceSerializationError("invalid_string", f"{path}.integrity")
    annotation_revisions = int(data.get("annotation_revisions", 0))
    lost_mark_count = int(data.get("lost_mark_count", 0))
    custodian_repository_id = _optional_entity("custodian_repository_id")

    try:
        return InformationArtifact(
            artifact_id=EntityId(_str_field(data, "artifact_id", path=path)),
            kind=ArtifactKind(_str_field(data, "kind", path=path)),
            author_id=EntityId(_str_field(data, "author_id", path=path)),
            created_tick=_nonneg_int_field(data, "created_tick", path=path),
            content=_decode_artifact_content(data["content"], path=f"{path}.content"),
            content_revision=_nonneg_int_field(data, "content_revision", path=path),
            location_id=location_id,
            holder_id=holder_id,
            record_genre=record_genre,
            parent_artifact_id=parent_artifact_id,
            source_artifact_id=source_artifact_id,
            copy_generation=copy_generation,
            integrity=integrity,
            annotation_revisions=annotation_revisions,
            lost_mark_count=lost_mark_count,
            custodian_repository_id=custodian_repository_id,
        )
    except DomainSerializationError as exc:
        raise _map_domain_error(exc) from exc
    except (TypeError, ValueError) as exc:
        raise PersistenceSerializationError("invalid_model", path) from exc



def _encode_knowledge_repository(value: KnowledgeRepository) -> dict[str, Any]:
    return {
        "access_mode": value.access_mode.value,
        "established_tick": value.established_tick,
        "founder_ids": [founder.value for founder in value.founder_ids],
        "index_entries": [
            {
                "artifact_id": None
                if entry.artifact_id is None
                else entry.artifact_id.value,
                "entry_id": entry.entry_id,
                "label_tokens": list(entry.label_tokens),
                "revision": entry.revision,
            }
            for entry in value.index_entries
        ],
        "last_maintained_tick": value.last_maintained_tick,
        "location_id": value.location_id.value,
        "member_artifact_ids": [mid.value for mid in value.member_artifact_ids],
        "neglect_streak": value.neglect_streak,
        "repository_id": value.repository_id.value,
        "status": value.status.value,
        "structure_id": None
        if value.structure_id is None
        else value.structure_id.value,
    }


def _decode_knowledge_repository(
    data: dict[str, Any], *, path: str
) -> KnowledgeRepository:
    _require_keys(
        data,
        {
            "repository_id",
            "location_id",
            "structure_id",
            "founder_ids",
            "established_tick",
            "access_mode",
            "status",
            "member_artifact_ids",
            "index_entries",
            "last_maintained_tick",
            "neglect_streak",
        },
        path=path,
    )
    structure_raw = data["structure_id"]
    structure_id = None if structure_raw is None else EntityId(str(structure_raw))
    founders_raw = data["founder_ids"]
    members_raw = data["member_artifact_ids"]
    entries_raw = data["index_entries"]
    if not isinstance(founders_raw, list) or not isinstance(members_raw, list):
        raise PersistenceSerializationError("invalid_fields", path)
    if not isinstance(entries_raw, list):
        raise PersistenceSerializationError("invalid_fields", path)
    entries: list[RepositoryIndexEntry] = []
    for index, raw in enumerate(entries_raw):
        if not isinstance(raw, dict):
            raise PersistenceSerializationError(
                "invalid_object", f"{path}.index_entries[{index}]"
            )
        art_raw = raw.get("artifact_id")
        art_id = None if art_raw is None else EntityId(str(art_raw))
        tokens = raw.get("label_tokens", [])
        if not isinstance(tokens, list):
            raise PersistenceSerializationError(
                "invalid_fields", f"{path}.index_entries[{index}]"
            )
        entries.append(
            RepositoryIndexEntry(
                entry_id=str(raw["entry_id"]),
                artifact_id=art_id,
                label_tokens=tuple(str(token) for token in tokens),
                revision=int(raw.get("revision", 0)),
            )
        )
    return KnowledgeRepository(
        repository_id=EntityId(_str_field(data, "repository_id", path=path)),
        location_id=EntityId(_str_field(data, "location_id", path=path)),
        founder_ids=tuple(EntityId(str(item)) for item in founders_raw),
        established_tick=_nonneg_int_field(data, "established_tick", path=path),
        access_mode=RepositoryAccessMode(_str_field(data, "access_mode", path=path)),
        status=RepositoryStatus(_str_field(data, "status", path=path)),
        structure_id=structure_id,
        member_artifact_ids=tuple(EntityId(str(item)) for item in members_raw),
        index_entries=tuple(entries),
        last_maintained_tick=_nonneg_int_field(
            data, "last_maintained_tick", path=path
        ),
        neglect_streak=_nonneg_int_field(data, "neglect_streak", path=path),
    )


def _encode_active_hazard(value: ActiveHazard) -> dict[str, Any]:
    return {
        "duration_ticks": value.duration_ticks,
        "kind": value.kind.value,
        "location_id": value.location_id.value,
        "start_tick": value.start_tick,
    }


def _decode_active_hazard(data: dict[str, Any], *, path: str) -> ActiveHazard:
    _require_keys(
        data,
        {"location_id", "kind", "start_tick", "duration_ticks"},
        path=path,
    )
    return ActiveHazard(
        EntityId(_str_field(data, "location_id", path=path)),
        HazardKind(_str_field(data, "kind", path=path)),
        _nonneg_int_field(data, "start_tick", path=path),
        _nonneg_int_field(data, "duration_ticks", path=path),
    )


def _encode_structure(value: Structure) -> dict[str, Any]:
    return {
        "entity_id": value.entity_id.value,
        "integrity": value.integrity,
        "kind": value.kind.value,
        "location_id": value.location_id.value,
        "stored_quantity": value.stored_quantity,
    }


def _decode_structure(data: dict[str, Any], *, path: str) -> Structure:
    _require_keys(
        data,
        {"entity_id", "location_id", "kind", "integrity", "stored_quantity"},
        path=path,
    )
    try:
        return Structure(
            entity_id=EntityId(_str_field(data, "entity_id", path=path)),
            location_id=EntityId(_str_field(data, "location_id", path=path)),
            kind=StructureKind(_str_field(data, "kind", path=path)),
            integrity=_float_field(data, "integrity", path=path),
            stored_quantity=_nonneg_int_field(data, "stored_quantity", path=path),
        )
    except PersistenceSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise PersistenceSerializationError("invalid_model", path) from exc


def _encode_production_job(value: ProductionJob) -> dict[str, Any]:
    return {
        "actor_id": value.actor_id.value,
        "created_item_id": value.created_item_id.value,
        "due_tick": value.due_tick,
        "duration_ticks": value.duration_ticks,
        "recipe_id": value.recipe_id.value,
    }


def _decode_production_job(data: dict[str, Any], *, path: str) -> ProductionJob:
    _require_keys(
        data,
        {"actor_id", "recipe_id", "due_tick", "created_item_id", "duration_ticks"},
        path=path,
    )
    try:
        return ProductionJob(
            actor_id=EntityId(_str_field(data, "actor_id", path=path)),
            recipe_id=RecipeId(_str_field(data, "recipe_id", path=path)),
            due_tick=_nonneg_int_field(data, "due_tick", path=path),
            created_item_id=EntityId(_str_field(data, "created_item_id", path=path)),
            duration_ticks=_nonneg_int_field(data, "duration_ticks", path=path),
        )
    except PersistenceSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise PersistenceSerializationError("invalid_model", path) from exc


def _encode_tool_mark(value: ToolMark) -> dict[str, Any]:
    return {"item_id": value.item_id.value, "role": value.role.value}


def _decode_tool_mark(data: dict[str, Any], *, path: str) -> ToolMark:
    _require_keys(data, {"item_id", "role"}, path=path)
    try:
        return ToolMark(
            item_id=EntityId(_str_field(data, "item_id", path=path)),
            role=ToolRole(_str_field(data, "role", path=path)),
        )
    except PersistenceSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise PersistenceSerializationError("invalid_model", path) from exc


def _encode_tick_commit(value: TickCommit) -> dict[str, Any]:
    return {
        "base_revision": value.base_revision.value,
        "commit_hash": value.commit_hash.value,
        "event_count": value.event_count,
        "idempotency_key": value.idempotency_key,
        "payload_hash": value.payload_hash.value,
        "predecessor_commit_hash": (
            None
            if value.predecessor_commit_hash is None
            else value.predecessor_commit_hash.value
        ),
        "resulting_revision": value.resulting_revision.value,
        "resulting_tick": value.resulting_tick.value,
        "run_id": value.run_id.value,
        "snapshot_id": None if value.snapshot_id is None else value.snapshot_id.value,
        "tick": value.tick.value,
    }


def _decode_tick_commit(data: dict[str, Any], *, path: str) -> TickCommit:
    _require_keys(
        data,
        {
            "run_id",
            "tick",
            "resulting_tick",
            "base_revision",
            "resulting_revision",
            "predecessor_commit_hash",
            "commit_hash",
            "idempotency_key",
            "event_count",
            "payload_hash",
            "snapshot_id",
        },
        path=path,
    )
    try:
        predecessor_raw = data["predecessor_commit_hash"]
        if predecessor_raw is None:
            predecessor = None
        elif isinstance(predecessor_raw, str):
            predecessor = CommitHash(predecessor_raw)
        else:
            raise PersistenceSerializationError(
                "invalid_string", f"{path}.predecessor_commit_hash"
            )
        snapshot_raw = data["snapshot_id"]
        if snapshot_raw is None:
            snapshot_id = None
        elif isinstance(snapshot_raw, str):
            snapshot_id = SnapshotId(snapshot_raw)
        else:
            raise PersistenceSerializationError("invalid_string", f"{path}.snapshot_id")
        return TickCommit(
            run_id=RunId(_str_field(data, "run_id", path=path)),
            tick=Tick(_nonneg_int_field(data, "tick", path=path)),
            resulting_tick=Tick(_nonneg_int_field(data, "resulting_tick", path=path)),
            base_revision=WorldRevision(
                _nonneg_int_field(data, "base_revision", path=path)
            ),
            resulting_revision=WorldRevision(
                _nonneg_int_field(data, "resulting_revision", path=path)
            ),
            predecessor_commit_hash=predecessor,
            commit_hash=CommitHash(_str_field(data, "commit_hash", path=path)),
            idempotency_key=_str_field(data, "idempotency_key", path=path),
            event_count=_nonneg_int_field(data, "event_count", path=path),
            payload_hash=PayloadHash(_str_field(data, "payload_hash", path=path)),
            snapshot_id=snapshot_id,
        )
    except PersistenceSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise PersistenceSerializationError("malformed_id", path) from exc


def _encode_world_event(value: WorldEvent, *, path: str) -> dict[str, Any]:
    try:
        require_replayable_event(value)
    except (TypeError, ValueError) as exc:
        raise PersistenceSerializationError("non_replayable_event", path) from exc
    try:
        payload: dict[str, Any] = {
            "actor_id": None if value.actor_id is None else value.actor_id.value,
            "details": _encode_event_details(value.details),
            "event_id": value.event_id.value,
            "event_type": value.event_type,
            "request_id": value.request_id.value,
            "resulting_revision": value.resulting_revision.value,
            "run_id": value.run_id,
            "schema_version": value.schema_version,
            "sequence": value.sequence,
            "target_id": None if value.target_id is None else value.target_id.value,
            "tick": value.tick,
            "world_id": value.world_id.value,
        }
        if value.cause is not None:
            payload["cause"] = _encode_event_cause(value.cause)
        if value.occurrence is not None:
            payload["occurrence"] = _encode_occurrence_context(value.occurrence)
        return payload
    except DomainSerializationError as exc:
        raise _map_domain_error(exc) from exc


def _encode_occurrence_context(value: OccurrenceContext) -> dict[str, Any]:
    return {
        "affected_entity_ids": [item.value for item in value.affected_entity_ids],
        "destination_location_id": (
            None
            if value.destination_location_id is None
            else value.destination_location_id.value
        ),
        "origin_location_id": (
            None if value.origin_location_id is None else value.origin_location_id.value
        ),
        "private_recipient_ids": [item.value for item in value.private_recipient_ids],
    }


def _decode_occurrence_context(data: dict[str, Any], *, path: str) -> OccurrenceContext:
    _require_keys(
        data,
        {
            "origin_location_id",
            "destination_location_id",
            "affected_entity_ids",
            "private_recipient_ids",
        },
        path=path,
    )
    origin_raw = data["origin_location_id"]
    destination_raw = data["destination_location_id"]
    affected_raw = data["affected_entity_ids"]
    private_raw = data["private_recipient_ids"]
    if not isinstance(affected_raw, list) or not isinstance(private_raw, list):
        raise PersistenceSerializationError("invalid_array", path)
    try:
        return OccurrenceContext(
            origin_location_id=(
                None
                if origin_raw is None
                else EntityId(_require_id_str(origin_raw, path))
            ),
            destination_location_id=(
                None
                if destination_raw is None
                else EntityId(_require_id_str(destination_raw, path))
            ),
            affected_entity_ids=tuple(
                EntityId(_require_id_str(item, f"{path}.affected_entity_ids"))
                for item in affected_raw
            ),
            private_recipient_ids=tuple(
                EntityId(_require_id_str(item, f"{path}.private_recipient_ids"))
                for item in private_raw
            ),
        )
    except (TypeError, ValueError) as exc:
        raise PersistenceSerializationError("malformed_id", path) from exc


def _decode_world_event(data: dict[str, Any], *, path: str) -> WorldEvent:
    base_keys = {
        "event_id",
        "run_id",
        "world_id",
        "tick",
        "sequence",
        "request_id",
        "resulting_revision",
        "schema_version",
        "details",
        "actor_id",
        "target_id",
        "event_type",
    }
    keys = set(data)
    allowed = {
        frozenset(base_keys),
        frozenset(base_keys | {"cause"}),
        frozenset(base_keys | {"cause", "occurrence"}),
    }
    if keys not in allowed:
        raise PersistenceSerializationError("invalid_fields", path)
    details_raw = data["details"]
    if not isinstance(details_raw, dict):
        raise PersistenceSerializationError("invalid_object", f"{path}.details")
    try:
        schema_version = _nonneg_int_field(data, "schema_version", path=path)
        if schema_version not in {
            EVENT_SCHEMA_REPLAY_V2,
            EVENT_SCHEMA_REPLAY_V3,
            EVENT_SCHEMA_REPLAY_V4,
            EVENT_SCHEMA_REPLAY_V5,
        }:
            raise PersistenceSerializationError(
                "unsupported_version",
                f"{path}.schema_version",
                version=schema_version,
            )
        actor_raw = data["actor_id"]
        target_raw = data["target_id"]
        actor_id = (
            None if actor_raw is None else EntityId(_require_id_str(actor_raw, path))
        )
        target_id = (
            None if target_raw is None else EntityId(_require_id_str(target_raw, path))
        )
        try:
            details = require_event_details(
                _decode_event_details(
                    details_raw,
                    path=f"{path}.details",
                    schema_version=schema_version,
                    speaker_id=actor_id,
                    event_id=_str_field(data, "event_id", path=path),
                )
            )
        except DomainSerializationError as exc:
            raise _map_domain_error(exc) from exc
        cause = None
        if "cause" in data:
            cause_raw = data["cause"]
            if not isinstance(cause_raw, dict):
                raise PersistenceSerializationError("invalid_object", f"{path}.cause")
            try:
                cause = _decode_event_cause(cause_raw, path=f"{path}.cause")
            except DomainSerializationError as exc:
                raise _map_domain_error(exc) from exc
        elif schema_version >= EVENT_SCHEMA_REPLAY_V3:
            raise PersistenceSerializationError("invalid_fields", f"{path}.cause")
        occurrence = None
        if "occurrence" in data:
            occurrence_raw = data["occurrence"]
            if not isinstance(occurrence_raw, dict):
                raise PersistenceSerializationError(
                    "invalid_object", f"{path}.occurrence"
                )
            occurrence = _decode_occurrence_context(
                occurrence_raw, path=f"{path}.occurrence"
            )
        elif schema_version >= EVENT_SCHEMA_REPLAY_V4:
            raise PersistenceSerializationError("invalid_fields", f"{path}.occurrence")
        event = WorldEvent(
            event_id=EventId(_str_field(data, "event_id", path=path)),
            run_id=_str_field(data, "run_id", path=path),
            world_id=WorldId(_str_field(data, "world_id", path=path)),
            tick=_nonneg_int_field(data, "tick", path=path),
            sequence=_nonneg_int_field(data, "sequence", path=path),
            request_id=RequestId(_str_field(data, "request_id", path=path)),
            resulting_revision=WorldRevision(
                _nonneg_int_field(data, "resulting_revision", path=path)
            ),
            schema_version=schema_version,
            details=details,
            actor_id=actor_id,
            target_id=target_id,
            cause=cause,  # type: ignore[arg-type]
            occurrence=occurrence,
        )
        if data["event_type"] != event.event_type:
            raise PersistenceSerializationError("invalid_fields", f"{path}.event_type")
        if not event_is_replayable(event):
            raise PersistenceSerializationError("non_replayable_event", path)
        return event
    except PersistenceSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise PersistenceSerializationError("malformed_id", path) from exc


def _require_id_str(raw: object, path: str) -> str:
    if not isinstance(raw, str):
        raise PersistenceSerializationError("invalid_string", path)
    return raw


def _decode_object_list(raw: object, decoder: Any, *, path: str) -> tuple[Any, ...]:
    if not isinstance(raw, list):
        raise PersistenceSerializationError("invalid_array", path)
    items = []
    for index, item in enumerate(raw):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict):
            raise PersistenceSerializationError("invalid_object", item_path)
        items.append(decoder(item, path=item_path))
    return tuple(items)


def _decode_domain_object_list(
    raw: object, decoder: Any, *, path: str
) -> tuple[Any, ...]:
    """Decode nested domain objects; map DomainSerializationError codes."""
    if not isinstance(raw, list):
        raise PersistenceSerializationError("invalid_array", path)
    items = []
    for index, item in enumerate(raw):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict):
            raise PersistenceSerializationError("invalid_object", item_path)
        try:
            items.append(decoder(item, path=item_path))
        except DomainSerializationError as exc:
            raise _map_domain_error(exc) from exc
    return tuple(items)
