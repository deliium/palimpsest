"""Signed lineage cursor purpose, scope and failure semantics."""

from __future__ import annotations

import base64
import json

import pytest

from api.lineage_cursor import CURSOR_TTL_SECONDS, LineageCursorCodec
from simulation.lineage_identity import LineageEvidenceClass, LineageFamily
from simulation.lineage_models import LineageError, LineageScope
from simulation.models import RunId

_SCOPE = LineageScope(
    run_id=RunId("run-cursor"),
    family=LineageFamily.GENEALOGY,
    evidence_class=LineageEvidenceClass.OBJECTIVE,
)
_OTHER = LineageScope(
    run_id=RunId("run-cursor"),
    family=LineageFamily.RECORD,
    evidence_class=LineageEvidenceClass.OBJECTIVE,
)


class _Clock:
    def __init__(self, value: float = 100.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


def _codec(clock: _Clock | None = None) -> LineageCursorCodec:
    return LineageCursorCodec(b"k" * 32, now=clock or _Clock())


def test_traverse_cursor_round_trip_and_scope_binding() -> None:
    codec = _codec()
    token = codec.encode_traverse(
        _SCOPE,
        snapshot_id="publication-1",
        snapshot_digest="a" * 64,
        snapshot_boundary_tick=5,
        root_key="b" * 64,
        query_fingerprint="c" * 64,
        record_offset=40,
    )
    payload = codec.decode(token, purpose="traverse", scope=_SCOPE)
    assert payload.record_offset == 40
    assert payload.snapshot_id == "publication-1"
    assert payload.scope == _SCOPE
    with pytest.raises(LineageError, match="invalid_lineage_cursor"):
        codec.decode(token, purpose="nodes", scope=_SCOPE)
    with pytest.raises(LineageError, match="invalid_lineage_cursor"):
        codec.decode(token, purpose="traverse", scope=_OTHER)


def test_node_and_snapshot_cursors_have_distinct_closed_fields() -> None:
    codec = _codec()
    nodes = codec.encode_nodes(
        _SCOPE,
        snapshot_id="publication-1",
        snapshot_digest="a" * 64,
        snapshot_boundary_tick=5,
        filter_fingerprint="d" * 64,
        last_node_key="e" * 64,
        page_size=100,
    )
    node_payload = codec.decode(nodes, purpose="nodes", scope=_SCOPE)
    assert node_payload.last_node_key == "e" * 64
    assert node_payload.root_key is None
    snapshots = codec.encode_snapshots(
        _SCOPE,
        run_commit_ref="commit-1",
        catalogue_generation="generation-1",
        last_boundary_key=5,
        last_publication_id="f" * 64,
        page_size=100,
    )
    snapshot_payload = codec.decode(snapshots, purpose="snapshots", scope=_SCOPE)
    assert snapshot_payload.last_boundary_key == 5
    assert snapshot_payload.snapshot_id is None


def test_tamper_expiry_and_rotation_are_rejected() -> None:
    clock = _Clock(100.0)
    codec = _codec(clock)
    token = codec.encode_traverse(
        _SCOPE,
        snapshot_id="publication-1",
        snapshot_digest="a" * 64,
        snapshot_boundary_tick=5,
        root_key="b" * 64,
        query_fingerprint="c" * 64,
        record_offset=0,
    )
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(LineageError, match="invalid_lineage_cursor"):
        codec.decode(tampered, purpose="traverse", scope=_SCOPE)
    clock.value += CURSOR_TTL_SECONDS + 1
    with pytest.raises(LineageError, match="lineage_cursor_expired"):
        codec.decode(token, purpose="traverse", scope=_SCOPE)
    rotated = LineageCursorCodec(b"z" * 32, now=_Clock(100.0))
    with pytest.raises(LineageError, match="invalid_lineage_cursor"):
        rotated.decode(token, purpose="traverse", scope=_SCOPE)


def test_signed_duplicate_deep_json_and_oversize_are_rejected() -> None:
    key = b"k" * 32
    clock = _Clock()
    codec = _codec(clock)
    duplicate = json.dumps(
        {
            "v": 1,
            "purpose": "traverse",
            "run": _SCOPE.run_id.value,
            "family": "genealogy",
            "class": "objective",
            "owner": None,
            "iat": 100,
            "exp": 1000,
            "snapshot_id": "publication-1",
            "snapshot_digest": "a" * 64,
            "root_key": "b" * 64,
            "qf": "c" * 64,
            "offset": 0,
        }
    ).replace('"offset": 0', '"offset": 0, "offset": 1')
    import hashlib
    import hmac

    body = base64.urlsafe_b64encode(duplicate.encode()).rstrip(b"=").decode()
    mac = (
        base64.urlsafe_b64encode(
            hmac.new(key, body.encode("ascii"), hashlib.sha256).digest()
        )
        .rstrip(b"=")
        .decode()
    )
    with pytest.raises(LineageError, match="invalid_lineage_cursor"):
        codec.decode(f"{body}.{mac}", purpose="traverse", scope=_SCOPE)
    deep: dict[str, object] = {}
    cursor = deep
    for _ in range(33):
        child: dict[str, object] = {}
        cursor["x"] = child
        cursor = child
    body = base64.urlsafe_b64encode(json.dumps(deep).encode()).rstrip(b"=").decode()
    mac = (
        base64.urlsafe_b64encode(
            hmac.new(key, body.encode("ascii"), hashlib.sha256).digest()
        )
        .rstrip(b"=")
        .decode()
    )
    with pytest.raises(LineageError, match="invalid_lineage_cursor"):
        codec.decode(f"{body}.{mac}", purpose="traverse", scope=_SCOPE)
    with pytest.raises(LineageError, match="invalid_lineage_cursor"):
        codec.decode("x" * 5000, purpose="traverse", scope=_SCOPE)


def test_participant_cursor_round_trip_and_cross_purpose_rejection() -> None:
    codec = _codec()
    token = codec.encode_participants(
        _SCOPE,
        snapshot_id="publication-1",
        snapshot_digest="a" * 64,
        snapshot_boundary_tick=5,
        filter_fingerprint="d" * 64,
        last_node_key="e" * 64,
        page_size=100,
    )
    payload = codec.decode(token, purpose="participants", scope=_SCOPE)
    assert payload.last_node_key == "e" * 64
    assert payload.filter_fingerprint == "d" * 64
    assert payload.snapshot_boundary_tick == 5
    for purpose in ("nodes", "snapshots", "traverse"):
        with pytest.raises(LineageError, match="invalid_lineage_cursor"):
            codec.decode(token, purpose=purpose, scope=_SCOPE)
    nodes = codec.encode_nodes(
        _SCOPE,
        snapshot_id="publication-1",
        snapshot_digest="a" * 64,
        snapshot_boundary_tick=5,
        filter_fingerprint="d" * 64,
        last_node_key="e" * 64,
        page_size=100,
    )
    with pytest.raises(LineageError, match="invalid_lineage_cursor"):
        codec.decode(nodes, purpose="participants", scope=_SCOPE)
