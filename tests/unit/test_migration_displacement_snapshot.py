# mypy: ignore-errors
"""migration-displacement-snapshot-v1 bounds, refs, digest, and codec."""

from __future__ import annotations

import dataclasses
import json

import pytest

from simulation.migration_displacement_codec import (
    MIGRATION_DISPLACEMENT_TOP_LEVEL_KEYS,
    decode_migration_displacement_snapshot,
    encode_migration_displacement_snapshot,
    finalize_migration_displacement_snapshot,
    migration_displacement_publication_id,
    migration_displacement_snapshot_digest,
)
from simulation.migration_displacement_models import (
    MIGRATION_DISPLACEMENT_FORBIDDEN_FIELD_NAMES,
    MIGRATION_DISPLACEMENT_MAX_BYTES,
    MIGRATION_DISPLACEMENT_MAX_CANDIDATES,
    MIGRATION_DISPLACEMENT_SNAPSHOT_POLICY,
    MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION,
    MigrationAlignmentSnapshotRow,
    MigrationCauseSnapshotRow,
    MigrationDisplacementCandidateRow,
    MigrationDisplacementSnapshot,
    MigrationDisplacementSummaryRow,
    MigrationLineageSnapshotRow,
    MigrationMovementRow,
    MigrationOutcomeSnapshotRow,
    MigrationWaveSnapshotRow,
    empty_migration_displacement_snapshot,
)

DIGEST = "a" * 64
CANDIDATE = "mig-" + ("b" * 32)


def _summary(**overrides):
    values = {
        "run_id": "run-1",
        "publication_id": "md-pub-" + ("c" * 32),
        "digest": DIGEST,
        "schema_version": MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION,
        "policy_version": MIGRATION_DISPLACEMENT_SNAPSHOT_POLICY,
    }
    values.update(overrides)
    return MigrationDisplacementSummaryRow(**values)


def _snapshot(**overrides) -> MigrationDisplacementSnapshot:
    values = {
        "summary": _summary(),
        "digest": DIGEST,
        "publication_id": "md-pub-" + ("c" * 32),
        "schema_version": MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION,
        "policy_version": MIGRATION_DISPLACEMENT_SNAPSHOT_POLICY,
    }
    values.update(overrides)
    return MigrationDisplacementSnapshot(**values)


def _candidate(**overrides) -> MigrationDisplacementCandidateRow:
    values = {
        "candidate_token": CANDIDATE,
        "kind": "wave",
        "status": "observed",
        "first_tick": 0,
        "last_tick": 1,
        "member_count": 2,
        "origin_token": "mdl-origin",
        "destination_token": "mdl-dest",
        "classification": "unknown",
        "coverage": "complete",
    }
    values.update(overrides)
    return MigrationDisplacementCandidateRow(**values)


def test_snapshot_requires_a_summary_row() -> None:
    empty = empty_migration_displacement_snapshot(
        "run-1", digest=DIGEST, publication_id="md-pub-" + ("c" * 32)
    )
    assert empty.summary.candidate_count == 0
    assert type(empty.summary) is MigrationDisplacementSummaryRow
    with pytest.raises(TypeError):
        MigrationDisplacementSnapshot(summary=None)  # type: ignore[arg-type]


def test_summary_counts_match_rows() -> None:
    wave = MigrationWaveSnapshotRow(
        wave_token="mdw-1",
        origin_token="mdl-a",
        destination_token="mdl-b",
        participant_tokens=("mdo-1", "mdo-2"),
        route_tokens=("mdl-a", "mdl-b"),
        start_tick=0,
        end_tick=2,
        cause_support_counts=(("conflict", 1),),
        displacement_classification="displacement_like",
        displacement_bases=("coercion",),
        independent_cause_count=1,
        cluster_tokens=(),
        coverage="complete",
    )
    with pytest.raises(ValueError, match="summary_counts"):
        _snapshot(waves=(wave,), summary=_summary(wave_count=0))
    valid = _snapshot(
        waves=(wave,),
        summary=_summary(wave_count=1, displacement_like_count=1, unknown_count=0),
    )
    assert valid.summary.wave_count == 1
    assert valid.summary.displacement_like_count == 1


def test_every_lineage_and_alignment_token_resolves() -> None:
    candidate = _candidate()
    with pytest.raises(ValueError, match="unresolved_candidate"):
        _snapshot(
            candidates=(candidate,),
            alignment=(
                MigrationAlignmentSnapshotRow(
                    "mown-1",
                    "mig-" + ("d" * 32),
                    "unresolved",
                    "cause",
                ),
            ),
            summary=_summary(candidate_count=1),
        )
    with pytest.raises(ValueError, match="unresolved_candidate"):
        _snapshot(
            candidates=(candidate,),
            lineage=(
                MigrationLineageSnapshotRow(
                    "mig-" + ("e" * 32),
                    "none",
                    "emerged",
                    0,
                    0,
                ),
            ),
            summary=_summary(candidate_count=1),
        )
    snapshot = _snapshot(
        candidates=(candidate,),
        lineage=(
            MigrationLineageSnapshotRow(CANDIDATE, "none", "emerged", 0, 0),
        ),
        alignment=(
            MigrationAlignmentSnapshotRow("mown-1", CANDIDATE, "consistent", "cause"),
        ),
        summary=_summary(candidate_count=1),
    )
    assert snapshot.lineage[0].relation == "emerged"


def test_closed_labels_and_token_grammar() -> None:
    with pytest.raises(ValueError, match="unknown_label"):
        MigrationCauseSnapshotRow(
            "mown-1",
            "mdc-1",
            "forced_displacement",
            "direct_observation",
            "",
            0.5,
            0,
            "active",
        )
    with pytest.raises(ValueError, match="invalid_token"):
        MigrationMovementRow(
            "BAD_TOKEN",
            "mdl-a",
            "mdl-b",
            ("mdl-a", "mdl-b"),
            0,
            1,
            "move",
            1,
            "arrived",
            "complete",
        )


def test_no_raw_identity_or_free_text_is_accepted() -> None:
    for row_type in (
        MigrationDisplacementSummaryRow,
        MigrationDisplacementCandidateRow,
        MigrationMovementRow,
        MigrationCauseSnapshotRow,
        MigrationWaveSnapshotRow,
        MigrationOutcomeSnapshotRow,
        MigrationAlignmentSnapshotRow,
    ):
        names = {item.name for item in dataclasses.fields(row_type)}
        assert names.isdisjoint(MIGRATION_DISPLACEMENT_FORBIDDEN_FIELD_NAMES)
    with pytest.raises(ValueError, match="out_of_range"):
        MigrationCauseSnapshotRow(
            "mown-1",
            "mdc-1",
            "conflict",
            "direct_observation",
            "",
            1.5,
            0,
            "active",
        )


def test_row_caps_are_enforced() -> None:
    candidates = tuple(
        _candidate(
            candidate_token=f"mig-{index:032x}",
            first_tick=index,
            last_tick=index,
        )
        for index in range(MIGRATION_DISPLACEMENT_MAX_CANDIDATES + 1)
    )
    with pytest.raises(ValueError, match="cap:candidates"):
        _snapshot(
            candidates=candidates,
            summary=_summary(candidate_count=len(candidates)),
        )


def test_canonical_digest_and_publication_id_are_stable() -> None:
    empty = empty_migration_displacement_snapshot(
        "run-1", digest="", publication_id=""
    )
    first = migration_displacement_snapshot_digest(empty)
    second = migration_displacement_snapshot_digest(empty)
    assert first == second
    assert len(first) == 64
    assert migration_displacement_publication_id(first).startswith("md-pub-")
    assert len(migration_displacement_publication_id(first)) == len("md-pub-") + 32


def test_encode_decode_round_trip() -> None:
    empty = empty_migration_displacement_snapshot(
        "run-1", digest="", publication_id=""
    )
    finalized = finalize_migration_displacement_snapshot(empty)
    encoded = encode_migration_displacement_snapshot(finalized)
    assert encoded.endswith(b"\n")
    assert encoded.count(b"\n") == 1
    assert set(dataclasses.asdict(finalized)) == MIGRATION_DISPLACEMENT_TOP_LEVEL_KEYS
    assert decode_migration_displacement_snapshot(encoded) == finalized


def test_oversize_payload_is_rejected() -> None:
    with pytest.raises(ValueError, match="migration_displacement_size_limit"):
        decode_migration_displacement_snapshot(
            b"x" * (MIGRATION_DISPLACEMENT_MAX_BYTES + 1)
        )


def test_existing_snapshots_are_unchanged() -> None:
    from simulation.borders_models import BORDERS_SNAPSHOT_SCHEMA
    from simulation.organized_conflict_models import (
        ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA,
    )

    assert MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION == (
        "migration-displacement-snapshot-v1"
    )
    assert BORDERS_SNAPSHOT_SCHEMA == "borders-snapshot-v1"
    assert ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA == "organized-conflict-snapshot-v1"
    assert MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION != BORDERS_SNAPSHOT_SCHEMA
    assert (
        MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION != ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA
    )


def test_unknown_keys_are_rejected() -> None:
    empty = finalize_migration_displacement_snapshot(
        empty_migration_displacement_snapshot(
            "run-1", digest="", publication_id=""
        )
    )
    payload = json.loads(encode_migration_displacement_snapshot(empty))
    payload["unknown_key"] = 1
    with pytest.raises(ValueError, match="unknown_key"):
        decode_migration_displacement_snapshot(json.dumps(payload).encode("utf-8"))
