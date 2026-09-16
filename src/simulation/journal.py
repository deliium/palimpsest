"""Canonical persistence codec and commit-hash chain helpers.

Strict UTF-8 JSON with deterministic key ordering. Codecs and hashing are
log-free; errors expose only ``code``, ``path``, and optional ``version``.
Never embed documents, payloads, seeds, or configuration values in messages.

Persistence types are intentionally separate from schema-v1 ``encode_domain``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Final

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.models import RunId, SimulationRunConfig
from simulation.persistence import (
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
    _decode_event_details,
    _decode_item,
    _decode_location,
    _decode_resource,
    _decode_weather,
    _encode_agent_body,
    _encode_event_details,
    _encode_item,
    _encode_location,
    _encode_resource,
    _encode_weather,
)
from world.events import (
    EVENT_SCHEMA_REPLAY_V1,
    WorldEvent,
    event_is_replayable,
    require_event_details,
    require_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

_TYPE_RUN_MANIFEST: Final[str] = "run_manifest"
_TYPE_WORLD_SNAPSHOT: Final[str] = "world_snapshot"
_TYPE_TICK_COMMIT: Final[str] = "tick_commit"
_TYPE_WORLD_EVENT: Final[str] = "world_event"

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
    "decode_persistence",
    "encode_persistence",
    "hash_snapshot",
    "hash_tick_events",
    "hash_tick_payload",
    "hash_world_event",
    "payload_hash",
    "verify_commit_chain",
]


class PersistenceSerializationError(ValueError):
    """Fail-closed persistence codec error with stable metadata only."""

    def __init__(
        self, code: str, path: str, version: str | int | None = None
    ) -> None:
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
    if version != PERSISTENCE_CODEC_VERSION:
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
        raise PersistenceSerializationError(
            "invalid_type", "$.predecessor_commit_hash"
        )
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
            None
            if predecessor_commit_hash is None
            else predecessor_commit_hash.value
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
                raise PersistenceSerializationError(
                    "commit_chain_gap", f"{path}.tick"
                )
            if commit.predecessor_commit_hash != previous.commit_hash:
                raise PersistenceSerializationError(
                    "predecessor_mismatch", f"{path}.predecessor_commit_hash"
                )
        previous = commit


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
    return {"seed": _encode_seed(config.seed)}


def _decode_config(data: dict[str, Any], *, path: str) -> SimulationRunConfig:
    _require_keys(data, {"seed"}, path=path)
    try:
        return SimulationRunConfig(seed=_nonneg_int_field(data, "seed", path=path))
    except PersistenceSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise PersistenceSerializationError("invalid_model", path) from exc


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
            "registrations": [
                _encode_registration(reg) for reg in value.registrations
            ],
            "resources": [_encode_resource(item) for item in value.resources],
            "revision": value.revision.value,
            "run_id": value.run_id.value,
            "seed": _encode_seed(value.seed),
            "snapshot_id": value.snapshot_id.value,
            "weather": [_encode_weather(item) for item in value.weather],
            "world_id": value.world_id.value,
        }
    except DomainSerializationError as exc:
        raise _map_domain_error(exc) from exc
    if include_integrity_hash:
        payload["integrity_hash"] = value.integrity_hash.value
    return payload


def _decode_world_snapshot(data: dict[str, Any], *, path: str) -> WorldSnapshot:
    _require_keys(
        data,
        {
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
        },
        path=path,
    )
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
        return WorldSnapshot(
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
        )
    except PersistenceSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise PersistenceSerializationError("malformed_id", path) from exc


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
            raise PersistenceSerializationError(
                "invalid_string", f"{path}.snapshot_id"
            )
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
        return {
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
    except DomainSerializationError as exc:
        raise _map_domain_error(exc) from exc


def _decode_world_event(data: dict[str, Any], *, path: str) -> WorldEvent:
    _require_keys(
        data,
        {
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
        },
        path=path,
    )
    details_raw = data["details"]
    if not isinstance(details_raw, dict):
        raise PersistenceSerializationError("invalid_object", f"{path}.details")
    try:
        try:
            details = require_event_details(
                _decode_event_details(details_raw, path=f"{path}.details")
            )
        except DomainSerializationError as exc:
            raise _map_domain_error(exc) from exc
        schema_version = _nonneg_int_field(data, "schema_version", path=path)
        if schema_version != EVENT_SCHEMA_REPLAY_V1:
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


def _decode_object_list(
    raw: object, decoder: Any, *, path: str
) -> tuple[Any, ...]:
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
