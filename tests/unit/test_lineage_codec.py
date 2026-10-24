"""Strict canonical codec tests for lineage-snapshot-v1 artifacts."""

from __future__ import annotations

import hashlib
import json

import pytest

from simulation.lineage_codec import (
    LINEAGE_MANIFEST_MAX_BYTES,
    LINEAGE_RECORD_MAX_BYTES,
    LineageAdjacencyPage,
    LineageControlRecord,
    LineageNodePage,
    LineageSnapshotManifest,
    compute_publication_id,
    decode_lineage_adjacency_page,
    decode_lineage_control_record,
    decode_lineage_manifest,
    decode_lineage_node_descriptor,
    decode_lineage_node_page,
    decode_lineage_publication,
    encode_lineage_adjacency_page,
    encode_lineage_control_record,
    encode_lineage_node_descriptor,
    encode_lineage_node_page,
    encode_lineage_publication,
)
from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageEvidenceRef,
    LineageFamily,
    LineageNativeKind,
    LineageNodeRef,
    lineage_edge_key,
)
from simulation.lineage_models import (
    LineageCoverage,
    LineageCoverageState,
    LineageDirection,
    LineageEdge,
    LineageError,
    LineageNode,
    LineageNodeState,
    LineageSnapshotRef,
)
from simulation.lineage_ports import LineageBoundaryFrame, LineagePublication
from simulation.models import RunId

_RUN = RunId("run-codec")


def _ref(native_id: str) -> LineageNodeRef:
    return LineageNodeRef(
        run_id=_RUN,
        family=LineageFamily.GENEALOGY,
        evidence_class=LineageEvidenceClass.OBJECTIVE,
        native_kind=LineageNativeKind.AGENT,
        native_id=native_id,
    )


def _node(native_id: str, *, living: bool = True) -> LineageNode:
    ref = _ref(native_id)
    return LineageNode(
        ref=ref,
        state=LineageNodeState.OBSERVED,
        living=living,
        observed_tick=1,
        status_code="alive",
        confidence_value=0.5,
        counts=(("child_count", 1),),
        evidence_refs=(
            LineageEvidenceRef(
                evidence_class=LineageEvidenceClass.OBJECTIVE,
                native_kind=LineageNativeKind.AGENT,
                native_id=f"body-{native_id}",
                observed_tick=1,
            ),
        ),
        source_observed_boundary=2,
    )


def _edge(parent: LineageNode, child: LineageNode) -> LineageEdge:
    evidence = LineageEvidenceRef(
        evidence_class=LineageEvidenceClass.OBJECTIVE,
        native_kind=LineageNativeKind.AGENT,
        native_id=f"edge-{parent.ref.native_id}-{child.ref.native_id}",
        observed_tick=1,
    )
    return LineageEdge(
        edge_key=lineage_edge_key(
            relation="parent_of",
            source_key=parent.key,
            target_key=child.key,
            native_kind=LineageNativeKind.AGENT,
            native_id=f"edge-{parent.ref.native_id}-{child.ref.native_id}",
            evidence_keys=(evidence.key,),
        ),
        source_key=parent.key,
        target_key=child.key,
        relation="parent_of",
        native_kind=LineageNativeKind.AGENT,
        native_id=f"edge-{parent.ref.native_id}-{child.ref.native_id}",
        evidence_refs=(evidence,),
        observed_tick=1,
        status_code="established",
    )


def _publication() -> LineagePublication:
    father = _node("father")
    child = _node("child", living=False)
    edge = _edge(father, child)
    scope = __import__(
        "simulation.lineage_models", fromlist=["LineageScope"]
    ).LineageScope(
        run_id=_RUN,
        family=LineageFamily.GENEALOGY,
        evidence_class=LineageEvidenceClass.OBJECTIVE,
    )
    coverage = LineageCoverage(
        state=LineageCoverageState.COMPLETE,
        capture_start_tick=0,
        capture_end_tick=2,
        policy_version="lineage-v1",
    )
    frame = LineageBoundaryFrame(
        run_id=_RUN,
        scope=scope,
        boundary_tick=2,
        observed_boundary=2,
        nodes=(father, child),
        edges=(edge,),
        coverage=coverage,
        source_revision="rev-1",
    )
    snapshot = LineageSnapshotRef(
        publication_id="placeholder",
        digest="a" * 64,
        boundary_tick=2,
    )
    return LineagePublication(snapshot=snapshot, frame=frame)


def _manifest() -> LineageSnapshotManifest:
    publication = _publication()
    files = encode_lineage_publication(publication)
    return decode_lineage_manifest(files["manifest.json"])


def test_node_descriptor_round_trip_is_byte_identical() -> None:
    node = _node("agent-1")
    encoded = encode_lineage_node_descriptor(node)
    assert (
        encode_lineage_node_descriptor(decode_lineage_node_descriptor(encoded))
        == encoded
    )
    assert encoded.endswith(b"\n")


def test_node_page_insertion_order_is_canonical() -> None:
    page = LineageNodePage(nodes=(_node("a"), _node("b")))
    other = LineageNodePage(nodes=(_node("b"), _node("a")))
    assert encode_lineage_node_page(page) == encode_lineage_node_page(other)
    assert encode_lineage_node_page(
        decode_lineage_node_page(encode_lineage_node_page(page))
    ) == encode_lineage_node_page(page)


def test_extra_or_unsupported_fields_are_rejected() -> None:
    encoded = encode_lineage_node_descriptor(_node("a"))
    document = json.loads(encoded)
    document["text"] = "forbidden"
    with pytest.raises(ValueError, match="lineage_record_invalid"):
        decode_lineage_node_descriptor(json.dumps(document).encode())
    document = json.loads(encoded)
    document["schema_version"] = "lineage-snapshot-v2"
    with pytest.raises(ValueError, match="lineage_record_invalid"):
        decode_lineage_node_descriptor(json.dumps(document).encode())


def test_duplicate_json_keys_are_rejected_at_top_level_and_nested() -> None:
    encoded = encode_lineage_node_descriptor(_node("a")).decode()
    duplicate_top = encoded.replace(
        '{"confidence_code"', '{"confidence_code":null,"confidence_code"', 1
    )
    with pytest.raises(LineageError, match="lineage_identity_conflict"):
        decode_lineage_node_descriptor(duplicate_top.encode())
    page = encode_lineage_node_page(LineageNodePage(nodes=(_node("a"),))).decode()
    duplicate_nested = page.replace(
        '"state":"observed"', '"state":"observed","state":"observed"', 1
    )
    with pytest.raises(LineageError, match="lineage_identity_conflict"):
        decode_lineage_node_page(duplicate_nested.encode())


def test_duplicate_conflicting_records_are_rejected() -> None:
    node = _node("a")
    with pytest.raises(LineageError, match="lineage_identity_conflict"):
        LineageNodePage(nodes=(node, node))


def test_depth_limit_and_invalid_envelopes() -> None:
    deep: dict[str, object] = {}
    cursor = deep
    for _ in range(33):
        child: dict[str, object] = {}
        cursor["x"] = child
        cursor = child
    with pytest.raises(ValueError, match="lineage_record_invalid"):
        decode_lineage_node_page(json.dumps(deep).encode())
    with pytest.raises(ValueError, match="lineage_record_invalid"):
        decode_lineage_node_descriptor(b"\xff\xfe")
    with pytest.raises(ValueError, match="lineage_record_invalid"):
        decode_lineage_node_descriptor(b'{"a":1} {}')
    with pytest.raises(ValueError, match="lineage_record_invalid"):
        decode_lineage_node_descriptor(b"[]")


def test_nonfinite_and_oversized_records_are_rejected() -> None:
    encoded = encode_lineage_node_descriptor(_node("a")).decode()
    nonfinite = encoded.replace('"confidence_value":0.5', '"confidence_value":NaN')
    with pytest.raises(ValueError, match="lineage_record_invalid"):
        decode_lineage_node_descriptor(nonfinite.encode())
    with pytest.raises(LineageError, match="lineage_record_oversize"):
        decode_lineage_node_descriptor(
            b"{" + b" " * (LINEAGE_RECORD_MAX_BYTES + 1) + b"}"
        )


def test_manifest_tampering_and_path_shaped_ids_are_rejected() -> None:
    publication = _publication()
    files = encode_lineage_publication(publication)
    manifest = decode_lineage_manifest(files["manifest.json"])
    assert manifest.node_count == 2
    assert manifest.publication_id == compute_publication_id(manifest)
    tampered = json.loads(files["manifest.json"])
    tampered["run_id"] = "other-run"
    with pytest.raises(LineageError, match="lineage_digest_mismatch"):
        decode_lineage_manifest(json.dumps(tampered).encode())
    with pytest.raises(ValueError, match="path-shaped"):
        LineageSnapshotManifest(
            run_id=_RUN,
            family=LineageFamily.GENEALOGY,
            evidence_class=LineageEvidenceClass.OBJECTIVE,
            owner_id=None,
            boundary_tick=2,
            publication_id="a" * 64,
            content_digest="b" * 64,
            source_revision="rev-1",
            policy_version="p1",
            coverage=manifest.coverage,
            node_count=0,
            edge_count=0,
            page_count=1,
            page_digests=(("../escape.json", "c" * 64),),
        )


def test_manifest_scope_requires_owner_exactly_for_subjective() -> None:
    coverage = LineageCoverage(state=LineageCoverageState.COMPLETE)
    with pytest.raises(LineageError, match="lineage_scope_mismatch"):
        LineageSnapshotManifest(
            run_id=_RUN,
            family=LineageFamily.MENTORSHIP,
            evidence_class=LineageEvidenceClass.SUBJECTIVE,
            owner_id=None,
            boundary_tick=2,
            publication_id="a" * 64,
            content_digest="b" * 64,
            source_revision="rev-1",
            policy_version="p1",
            coverage=coverage,
            node_count=0,
            edge_count=0,
            page_count=0,
            page_digests=(),
        )


def test_publication_round_trip_verifies_page_digests() -> None:
    publication = _publication()
    files = encode_lineage_publication(publication)
    decoded = decode_lineage_publication(files)
    assert len(decoded.frame.nodes) == 2
    assert len(decoded.frame.edges) == 1
    assert decoded.snapshot.boundary_tick == 2
    page_name = next(name for name in files if name.startswith("nodes/"))
    corrupted = dict(files)
    corrupted[page_name] = files[page_name] + b" "
    with pytest.raises(LineageError, match="lineage_digest_mismatch"):
        decode_lineage_publication(corrupted)


def test_adjacency_short_page_round_trip() -> None:
    publication = _publication()
    father, child = publication.frame.nodes
    edge = publication.frame.edges[0]
    page = LineageAdjacencyPage(
        direction=LineageDirection.BOTH,
        node_key=father.key,
        edges=(edge,),
    )
    encoded = encode_lineage_adjacency_page(page)
    decoded = decode_lineage_adjacency_page(encoded)
    assert decoded.node_key == father.key
    assert len(decoded.edges) == 1
    assert len(encoded) < LINEAGE_RECORD_MAX_BYTES
    assert child.key


def test_control_record_round_trip_and_limits() -> None:
    record = LineageControlRecord(
        schema_version="lineage-control-v1",
        run_id=_RUN,
        catalogue_generation="generation-1",
        committed_publication_id="a" * 64,
        committed_digest="b" * 64,
        quota_reservations=3,
        quota_artifact_bytes=1024,
    )
    encoded = encode_lineage_control_record(record)
    assert decode_lineage_control_record(encoded) == record
    with pytest.raises(LineageError, match="lineage_record_oversize"):
        decode_lineage_control_record(
            b"{" + b" " * (LINEAGE_RECORD_MAX_BYTES + 1) + b"}"
        )
    assert len(encoded) <= LINEAGE_MANIFEST_MAX_BYTES


def test_byte_packed_short_pages_and_digest_are_stable() -> None:
    publication = _publication()
    files = encode_lineage_publication(publication)
    first = {
        name: hashlib.sha256(content).hexdigest() for name, content in files.items()
    }
    second_files = encode_lineage_publication(_publication())
    second = {
        name: hashlib.sha256(content).hexdigest()
        for name, content in second_files.items()
    }
    assert first == second
