"""Canonical persistence codec and commit-hash chain contracts."""

from __future__ import annotations

import json
import math

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.journal import (
    PersistenceSerializationError,
    compute_commit_hash,
    decode_persistence,
    encode_persistence,
    hash_snapshot,
    hash_tick_events,
    hash_world_event,
    payload_hash,
    verify_commit_chain,
)
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    CommitHash,
    PayloadHash,
    RunManifest,
    SnapshotId,
    TickCommit,
    WorldSnapshot,
)
from simulation.serialization import DomainSerializationError, encode_domain
from world.events import Waited, make_replayable_event
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.models import AgentBody, LifeStatus, Location
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst

_HASH_A = "a" * 64
_HASH_B = "b" * 64
_HASH_C = "c" * 64
_HASH_D = "d" * 64


def _alive_body(
    entity_id: str = "body-1",
    *,
    location_id: str = "loc-1",
) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
    )


def _snapshot(*, seed: int = 7, integrity: str = _HASH_A) -> WorldSnapshot:
    return WorldSnapshot(
        snapshot_id=SnapshotId("snap-bootstrap"),
        run_id=RunId("run-1"),
        world_id=WorldId("world-1"),
        seed=seed,
        config=SimulationRunConfig(seed=seed),
        registrations=(AgentRegistration(AgentId("agent-1"), EntityId("body-1")),),
        locations=(Location(entity_id=EntityId("loc-1"), name="Camp"),),
        bodies=(_alive_body(),),
        items=(),
        resources=(),
        weather=(),
        next_tick=Tick(0),
        revision=WorldRevision(0),
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash(integrity),
        predecessor_commit_hash=None,
    )


def _manifest(*, seed: int = 7) -> RunManifest:
    return RunManifest(
        run_id=RunId("run-1"),
        world_id=WorldId("world-1"),
        seed=seed,
        config=SimulationRunConfig(seed=seed),
        derivation_version=DERIVATION_VERSION,
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
    )


def _event() -> object:
    return make_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=RequestId("req-1"),
        resulting_revision=WorldRevision(1),
        details=Waited(),
        actor_id=None,
    )


def _commit(
    *,
    tick: int,
    predecessor: CommitHash | None,
    commit: str,
    payload: str = _HASH_C,
) -> TickCommit:
    return TickCommit(
        run_id=RunId("run-1"),
        tick=Tick(tick),
        resulting_tick=Tick(tick + 1),
        base_revision=WorldRevision(tick),
        resulting_revision=WorldRevision(tick + 1),
        predecessor_commit_hash=predecessor,
        commit_hash=CommitHash(commit),
        idempotency_key=f"idem-{tick}",
        event_count=0,
        payload_hash=PayloadHash(payload),
        snapshot_id=None,
    )


def test_round_trip_run_manifest_snapshot_commit_and_event() -> None:
    large_seed = 2**100
    manifest = _manifest(seed=large_seed)
    snapshot = _snapshot(seed=large_seed)
    event = _event()
    commit = _commit(tick=0, predecessor=None, commit=_HASH_A)

    assert decode_persistence(encode_persistence(manifest), RunManifest) == manifest
    assert decode_persistence(encode_persistence(snapshot), WorldSnapshot) == snapshot
    assert decode_persistence(encode_persistence(commit), TickCommit) == commit
    assert decode_persistence(encode_persistence(event), "world_event") == event


def test_deterministic_bytes_and_hashes() -> None:
    event = _event()
    first = encode_persistence(event)
    second = encode_persistence(event)
    assert first == second
    assert hash_world_event(event) == payload_hash(first)
    assert hash_tick_events((event, event)) == (
        hash_world_event(event),
        hash_world_event(event),
    )
    snapshot = _snapshot()
    assert hash_snapshot(snapshot) == hash_snapshot(snapshot)


def test_large_seed_round_trips_without_int64_clamp() -> None:
    seed = 2**100
    manifest = _manifest(seed=seed)
    encoded = encode_persistence(manifest)
    decoded = decode_persistence(encoded, RunManifest)
    assert isinstance(decoded, RunManifest)
    assert decoded.seed == seed
    assert decoded.config.seed == seed
    assert str(seed) in encoded.decode("utf-8")


def test_duplicate_unknown_nonfinite_and_version_rejected() -> None:
    with pytest.raises(PersistenceSerializationError) as duplicate:
        decode_persistence(
            b'{"data":{"seed":1,"seed":2},"persistence_codec_version":"v1",'
            b'"type":"run_manifest"}',
            RunManifest,
        )
    assert duplicate.value.code == "duplicate_key"

    good = encode_persistence(_manifest())
    document = json.loads(good.decode("utf-8"))
    document["data"]["extra"] = "nope"
    with pytest.raises(PersistenceSerializationError) as unknown:
        decode_persistence(
            json.dumps(document, separators=(",", ":"), sort_keys=True).encode(),
            RunManifest,
        )
    assert unknown.value.code == "unknown_field"

    document = json.loads(good.decode("utf-8"))
    document["persistence_codec_version"] = "v999"
    with pytest.raises(PersistenceSerializationError) as version:
        decode_persistence(
            json.dumps(document, separators=(",", ":"), sort_keys=True).encode(),
            RunManifest,
        )
    assert version.value.code == "unsupported_version"
    assert version.value.version == "v999"

    # Non-finite float in nested resource quantity path via raw JSON injection.
    snapshot_doc = json.loads(encode_persistence(_snapshot()).decode("utf-8"))
    snapshot_doc["data"]["resources"] = [
        {
            "entity_id": "res-1",
            "location_id": "loc-1",
            "name": "Water",
            "quantity": math.nan,
            "unit": "L",
        }
    ]
    with pytest.raises(PersistenceSerializationError) as nonfinite:
        decode_persistence(
            json.dumps(
                snapshot_doc,
                allow_nan=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode(),
            WorldSnapshot,
        )
    assert nonfinite.value.code == "non_finite_number"


def test_malformed_id_rejected_without_leaking_value() -> None:
    document = json.loads(encode_persistence(_manifest()).decode("utf-8"))
    bad_id = " leading-space-id"
    document["data"]["run_id"] = bad_id
    with pytest.raises(PersistenceSerializationError) as err:
        decode_persistence(
            json.dumps(document, separators=(",", ":"), sort_keys=True).encode(),
            RunManifest,
        )
    assert err.value.code == "malformed_id"
    assert bad_id not in str(err.value)


def test_commit_chain_validates_and_rejects_gaps() -> None:
    first_hash = compute_commit_hash(
        predecessor_commit_hash=None,
        run_id=RunId("run-1"),
        tick=Tick(0),
        base_revision=WorldRevision(0),
        resulting_revision=WorldRevision(1),
        event_hashes=(),
        payload_hash=PayloadHash(_HASH_C),
    )
    second_hash = compute_commit_hash(
        predecessor_commit_hash=first_hash,
        run_id=RunId("run-1"),
        tick=Tick(1),
        base_revision=WorldRevision(1),
        resulting_revision=WorldRevision(2),
        event_hashes=(),
        payload_hash=PayloadHash(_HASH_D),
    )
    commits = (
        _commit(tick=0, predecessor=None, commit=first_hash.value, payload=_HASH_C),
        _commit(
            tick=1,
            predecessor=first_hash,
            commit=second_hash.value,
            payload=_HASH_D,
        ),
    )
    verify_commit_chain(commits)

    gapped = (
        commits[0],
        _commit(
            tick=3,
            predecessor=first_hash,
            commit=second_hash.value,
            payload=_HASH_D,
        ),
    )
    with pytest.raises(PersistenceSerializationError) as gap:
        verify_commit_chain(gapped)
    assert gap.value.code == "commit_chain_gap"

    broken = (
        commits[0],
        _commit(
            tick=1,
            predecessor=CommitHash(_HASH_B),
            commit=second_hash.value,
            payload=_HASH_D,
        ),
    )
    with pytest.raises(PersistenceSerializationError) as pred:
        verify_commit_chain(broken)
    assert pred.value.code == "predecessor_mismatch"


def test_compute_commit_hash_is_deterministic() -> None:
    kwargs = {
        "predecessor_commit_hash": None,
        "run_id": RunId("run-1"),
        "tick": Tick(0),
        "base_revision": WorldRevision(0),
        "resulting_revision": WorldRevision(1),
        "event_hashes": (PayloadHash(_HASH_A),),
        "payload_hash": PayloadHash(_HASH_B),
    }
    assert compute_commit_hash(**kwargs) == compute_commit_hash(**kwargs)


def test_hash_snapshot_excludes_integrity_field() -> None:
    base = _snapshot(integrity=_HASH_A)
    other = _snapshot(integrity=_HASH_B)
    assert hash_snapshot(base) == hash_snapshot(other)


def test_error_messages_omit_seeds_and_payload_bodies() -> None:
    secret_seed = 2**90 + 12345
    document = json.loads(encode_persistence(_manifest(seed=7)).decode("utf-8"))
    document["data"]["seed"] = -1
    with pytest.raises(PersistenceSerializationError) as err:
        decode_persistence(
            json.dumps(document, separators=(",", ":"), sort_keys=True).encode(),
            RunManifest,
        )
    message = str(err.value)
    assert str(secret_seed) not in message
    assert '"seed"' not in message
    assert err.value.code == "invalid_int"


def test_encode_domain_rejects_persistence_types() -> None:
    with pytest.raises(DomainSerializationError) as rejected:
        encode_domain(_snapshot())
    assert rejected.value.code == "unsupported_type"
    with pytest.raises(DomainSerializationError) as manifest:
        encode_domain(_manifest())
    assert manifest.value.code == "unsupported_type"
