# mypy: ignore-errors
"""borders-snapshot-v1 bounds, refs, sorting, and forbidden fields."""

from __future__ import annotations

import dataclasses

import pytest

from simulation.borders_codec import (
    BORDERS_TOP_LEVEL_KEYS,
    borders_publication_id,
    borders_snapshot_digest,
    decode_borders_snapshot,
    encode_borders_snapshot,
    finalize_borders_snapshot,
)
from simulation.borders_models import (
    BORDERS_MAX_LINEAGE_EDGES,
    BORDERS_SNAPSHOT_MAX_BYTES,
    BORDERS_SNAPSHOT_POLICY,
    BORDERS_SNAPSHOT_SCHEMA,
    BordersAlignmentRow,
    BordersCandidateRow,
    BordersClaimRow,
    BordersLineageRow,
    BordersMetricProvenanceRow,
    BordersPatternRow,
    BordersPhysicalRow,
    BordersRecognitionRow,
    BordersSnapshot,
    BordersSummaryRow,
    empty_borders_snapshot,
)

DIGEST = "a" * 64


def _summary(**overrides):
    values = {
        "run_id": "run-1",
        "publication_id": "bd-pub-1",
        "digest": DIGEST,
        "schema_version": BORDERS_SNAPSHOT_SCHEMA,
        "policy_version": BORDERS_SNAPSHOT_POLICY,
        "catalog_version": "metric-catalog-v1",
    }
    values.update(overrides)
    return BordersSummaryRow(**values)


def _snapshot(**overrides) -> BordersSnapshot:
    values = {
        "schema_version": BORDERS_SNAPSHOT_SCHEMA,
        "policy_version": BORDERS_SNAPSHOT_POLICY,
        "catalog_version": "metric-catalog-v1",
        "run_id": "run-1",
        "publication_id": "bd-pub-1",
        "digest": DIGEST,
        "summary": _summary(),
    }
    values.update(overrides)
    return BordersSnapshot(**values)


def test_schema_policy_and_caps_are_frozen() -> None:
    assert BORDERS_SNAPSHOT_SCHEMA == "borders-snapshot-v1"
    assert BORDERS_SNAPSHOT_POLICY == "borders-snapshot.v1"
    assert BORDERS_SNAPSHOT_MAX_BYTES == 4 * 1024 * 1024
    assert BORDERS_MAX_LINEAGE_EDGES == 32
    with pytest.raises(ValueError):
        BordersSummaryRow(
            run_id="run-1",
            publication_id="bd-pub-1",
            digest=DIGEST,
            schema_version="other",
            policy_version=BORDERS_SNAPSHOT_POLICY,
            catalog_version="metric-catalog-v1",
        )


def test_summary_is_required_and_counts_match() -> None:
    claim = BordersClaimRow(
        "bdc-1", "bown-1", "bdc-1", ("bloc-a",), (), "claimed", 0.8
    )
    with pytest.raises(ValueError):
        _snapshot(
            claims=(claim,),
            summary=_summary(claim_count=0),
        )
    valid = _snapshot(claims=(claim,), summary=_summary(claim_count=1))
    assert valid.summary.claim_count == 1


def test_rows_are_sorted_and_unique() -> None:
    first = BordersClaimRow(
        "bdc-1", "bown-1", "bdc-1", ("bloc-a",), (), "claimed", 0.8
    )
    second = BordersClaimRow(
        "bdc-2", "bown-1", "bdc-2", ("bloc-b",), (), "claimed", 0.8
    )
    with pytest.raises(ValueError):
        _snapshot(
            claims=(second, first),
            summary=_summary(claim_count=2),
        )
    with pytest.raises(ValueError):
        _snapshot(
            claims=(first, first),
            summary=_summary(claim_count=2),
        )


def test_domain_refs_must_resolve() -> None:
    pattern = BordersPatternRow(
        "bpat-1", "bdc-missing", ("bloc-a",), "claim_only"
    )
    with pytest.raises(ValueError):
        _snapshot(
            patterns=(pattern,),
            summary=_summary(pattern_count=1),
        )


def test_candidate_refs_must_resolve_for_lineage_and_alignment() -> None:
    candidate = BordersCandidateRow(
        "bord-0000000000000001", ("bloc-a",), (), "claimed", 1, 0, 0
    )
    alignment = BordersAlignmentRow(
        "bord-0000000000000002",
        "unresolved",
        "consistent",
        "unresolved",
        "unresolved",
    )
    with pytest.raises(ValueError):
        _snapshot(
            candidates=(candidate,),
            alignment=(alignment,),
            summary=_summary(candidate_count=1),
        )
    terminal = BordersLineageRow(
        "bord-edge-1",
        "bord-start-0000000000000001",
        candidate.candidate_token,
        "emerged",
        0,
        0,
    )
    snapshot = _snapshot(
        candidates=(candidate,),
        lineage=(terminal,),
        summary=_summary(candidate_count=1),
    )
    assert snapshot.lineage[0].kind == "emerged"


def test_forbidden_fields_and_raw_ids_are_rejected() -> None:
    from simulation.borders_models import BORDERS_FORBIDDEN_FIELD_NAMES

    for row_type in (
        BordersClaimRow,
        BordersRecognitionRow,
        BordersCandidateRow,
        BordersPatternRow,
        BordersPhysicalRow,
        BordersMetricProvenanceRow,
    ):
        names = {item.name for item in dataclasses.fields(row_type)}
        assert names.isdisjoint(BORDERS_FORBIDDEN_FIELD_NAMES)
    with pytest.raises(ValueError):
        BordersClaimRow(
            "bdc-1", "bown-1", "bdc-1", ("bloc-a",), (), "claimed", 1.5
        )


def test_empty_and_full_snapshots_validate() -> None:
    empty = empty_borders_snapshot(
        "run-1", publication_id="bd-pub-1", digest=DIGEST
    )
    assert empty.summary.claim_count == 0
    physical = BordersPhysicalRow("bloc-a", 0, 5, 1, 2, 0, 0, 2, "repeated_use")
    claim = BordersClaimRow(
        "bdc-1", "bown-1", "bdc-1", ("bloc-a",), (), "claimed", 0.8
    )
    pattern = BordersPatternRow(
        "bpat-1", "bdc-1", ("bloc-a",), "claim_only"
    )
    full = _snapshot(
        physical=(physical,),
        claims=(claim,),
        patterns=(pattern,),
        summary=_summary(claim_count=1, physical_row_count=1, pattern_count=1),
    )
    assert len(full.claims) == 1


def test_existing_snapshots_are_unchanged() -> None:
    from simulation.organized_conflict_models import (
        ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA,
    )

    assert ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA == "organized-conflict-snapshot-v1"
    assert BORDERS_SNAPSHOT_SCHEMA != ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA


def test_codec_digest_and_round_trip() -> None:
    empty = empty_borders_snapshot(
        "run-1", publication_id="bd-pub-1", digest=DIGEST
    )
    digest = borders_snapshot_digest(empty)
    assert len(digest) == 64
    assert BORDERS_TOP_LEVEL_KEYS == set(
        dataclasses.asdict(empty)
    )
    finalized = finalize_borders_snapshot(empty)
    assert finalized.publication_id == borders_publication_id(finalized.digest)
    encoded = encode_borders_snapshot(finalized)
    assert len(encoded) <= BORDERS_SNAPSHOT_MAX_BYTES
    assert decode_borders_snapshot(encoded) == finalized


def test_unknown_keys_and_size_limits() -> None:
    import json

    empty = finalize_borders_snapshot(
        empty_borders_snapshot("run-1", publication_id="bd-pub-1", digest=DIGEST)
    )
    payload = json.loads(encode_borders_snapshot(empty))
    payload["unknown_key"] = 1
    with pytest.raises(ValueError):
        decode_borders_snapshot(json.dumps(payload).encode("utf-8"))
    with pytest.raises(ValueError):
        decode_borders_snapshot(b"x" * (BORDERS_SNAPSHOT_MAX_BYTES + 1))


def test_metric_provenance_has_value_keys() -> None:
    row = BordersMetricProvenanceRow(
        "border_claim_structure", "1", "metric-catalog-v1", ("domain_count",)
    )
    assert row.value_keys == ("domain_count",)
