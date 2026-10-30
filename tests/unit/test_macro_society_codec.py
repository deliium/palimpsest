"""Snapshot codec, paging, and port contracts."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from simulation.macro_society_codec import (
    compute_macro_society_publication_id,
    decode_macro_society_snapshot,
    encode_macro_society_snapshot,
    encode_macro_society_value,
    macro_society_digest,
)
from simulation.macro_society_models import (
    MACRO_SOCIETY_SNAPSHOT_SCHEMA_VERSION,
    MacroSocietyArtifactError,
    MacroSocietyCandidateRecord,
    MacroSocietyCoverage,
    MacroSocietyLineageEdgeRecord,
    MacroSocietyObjectiveRow,
    MacroSocietySnapshot,
    MacroSocietyWindowRecord,
)
from simulation.macro_society_paging import (
    MAX_PAGE_ROWS,
    select_macro_society_rows,
)
from simulation.macro_society_ports import (
    MacroSocietyCursor,
    MacroSocietyPublication,
    MacroSocietyReadSession,
    macro_society_query_fingerprint,
)

ROOT = Path(__file__).resolve().parents[2]

CANDIDATE_ID = "msoc-0123456789abcdef"
SECOND_ID = "msoc-fedcba9876543210"
MEMBERS = ("person-1", "person-2", "person-3", "person-4")


def _snapshot(
    publication_id: str = "msoc-edge-0123456789abcdef",
) -> MacroSocietySnapshot:
    return MacroSocietySnapshot(
        schema_version=MACRO_SOCIETY_SNAPSHOT_SCHEMA_VERSION,
        policy_version="macro-society-identity.v1",
        run_id="run-1",
        input_revision="rev-1",
        generated_tick=10,
        publication_id=publication_id,
        windows=(
            MacroSocietyWindowRecord(
                0,
                0,
                9,
                (CANDIDATE_ID,),
                0,
                len(MEMBERS),
                (("culture", True), ("interaction", False)),
            ),
        ),
        candidates=(
            MacroSocietyCandidateRecord(
                CANDIDATE_ID,
                0,
                0,
                9,
                "supported",
                MEMBERS,
                ("culture",),
            ),
        ),
        edges=(),
        objective_rows=(MacroSocietyObjectiveRow("region-a", 0, len(MEMBERS)),),
        coverage=MacroSocietyCoverage(len(MEMBERS), len(MEMBERS), 1.0),
        provenance_code="ok",
    )


def test_snapshot_round_trips_byte_for_byte() -> None:
    snapshot = _snapshot()
    payload = encode_macro_society_snapshot(snapshot)
    assert decode_macro_society_snapshot(payload) == snapshot
    decoded = decode_macro_society_snapshot(payload)
    assert encode_macro_society_snapshot(decoded) == payload


def test_unknown_and_missing_keys_fail_closed() -> None:
    payload = encode_macro_society_snapshot(_snapshot())
    data = json.loads(payload)
    data["unexpected"] = True
    with pytest.raises(MacroSocietyArtifactError, match="macro_society_unknown_field"):
        decode_macro_society_snapshot(
            json.dumps(data, sort_keys=True).encode("utf-8")
        )

    data = json.loads(payload)
    del data["policy_version"]
    with pytest.raises(MacroSocietyArtifactError, match="macro_society_missing_field"):
        decode_macro_society_snapshot(
            json.dumps(data, sort_keys=True).encode("utf-8")
        )


def test_duplicate_json_keys_and_non_finite_values_fail_closed() -> None:
    payload = encode_macro_society_snapshot(_snapshot()).decode("utf-8")
    duplicated = payload.replace(
        '"run_id":"run-1"', '"run_id":"run-1","run_id":"run-1"'
    )
    with pytest.raises(MacroSocietyArtifactError, match="macro_society_duplicate_key"):
        decode_macro_society_snapshot(duplicated.encode("utf-8"))

    with pytest.raises(MacroSocietyArtifactError, match="macro_society_invalid_value"):
        decode_macro_society_snapshot(
            payload.replace('"generated_tick":10', '"generated_tick":NaN').encode(
                "utf-8"
            )
        )


def test_oversized_payload_fails_closed() -> None:
    with pytest.raises(MacroSocietyArtifactError, match="macro_society_size_limit"):
        decode_macro_society_snapshot(b"{" + b" " * (4 * 1024 * 1024 + 1) + b"}")


def test_digest_and_publication_id_are_stable_and_bound() -> None:
    payload = encode_macro_society_snapshot(_snapshot())
    assert macro_society_digest(json.loads(payload)) == macro_society_digest(
        json.loads(payload)
    )
    first = compute_macro_society_publication_id(payload, run_id="run-1")
    assert first.startswith("msoc-edge-") and len(first) == len("msoc-edge-") + 16
    assert first == compute_macro_society_publication_id(payload, run_id="run-1")
    assert first != compute_macro_society_publication_id(payload, run_id="run-2")


def test_snapshot_rejects_edge_endpoint_cycles_of_unknown_ids() -> None:
    with pytest.raises(
        MacroSocietyArtifactError, match="macro_society_unknown_society"
    ):
        MacroSocietySnapshot(
            schema_version=MACRO_SOCIETY_SNAPSHOT_SCHEMA_VERSION,
            policy_version="macro-society-identity.v1",
            run_id="run-1",
            input_revision="rev-1",
            generated_tick=10,
            publication_id="msoc-edge-0123456789abcdef",
            windows=(),
            candidates=(),
            edges=(
                MacroSocietyLineageEdgeRecord(
                    CANDIDATE_ID, SECOND_ID, "continued", 0, 10, 1.0
                ),
            ),
            objective_rows=(),
            coverage=MacroSocietyCoverage(0, 0, None),
            provenance_code="ok",
        )


def test_paging_is_bounded_and_reports_next_offset() -> None:
    rows = tuple({"index": index} for index in range(10))
    first = select_macro_society_rows(rows, offset=0, limit=4, max_bytes=4096)
    assert len(first.rows) == 4
    assert first.next_offset == 4
    second = select_macro_society_rows(rows, offset=4, limit=4, max_bytes=4096)
    assert len(second.rows) == 4
    last = select_macro_society_rows(rows, offset=8, limit=4, max_bytes=4096)
    assert len(last.rows) == 2
    assert last.next_offset is None


def test_paging_clamps_limit_and_returns_one_oversized_row() -> None:
    rows = tuple({"index": index} for index in range(MAX_PAGE_ROWS + 50))
    page = select_macro_society_rows(rows, offset=0, limit=10_000, max_bytes=1)
    assert len(page.rows) == 1
    assert page.next_offset == 1
    assert page.bytes_used == len(encode_macro_society_value(rows[0]))


def test_paging_rejects_invalid_arguments() -> None:
    with pytest.raises(MacroSocietyArtifactError, match="macro_society_invalid_offset"):
        select_macro_society_rows((), offset=-1, limit=1, max_bytes=10)
    with pytest.raises(MacroSocietyArtifactError, match="macro_society_invalid_limit"):
        select_macro_society_rows((), offset=0, limit=0, max_bytes=10)


def test_cursor_and_fingerprint_are_purpose_and_content_bound() -> None:
    fingerprint = macro_society_query_fingerprint(
        run_id="run-1",
        publication_id="msoc-edge-0123456789abcdef",
        purpose="candidates",
        filters={"status": "supported"},
    )
    cursor = MacroSocietyCursor(
        purpose="candidates",
        run_id="run-1",
        publication_id="msoc-edge-0123456789abcdef",
        snapshot_digest="a" * 64,
        offset=10,
        query_fingerprint=fingerprint,
    )
    assert cursor.query_fingerprint == fingerprint
    assert (
        macro_society_query_fingerprint(
            run_id="run-1",
            publication_id="msoc-edge-0123456789abcdef",
            purpose="candidates",
            filters={"status": "fragmented"},
        )
        != fingerprint
    )


def test_read_session_enforces_the_response_cap() -> None:
    session = MacroSocietyReadSession(
        publication_id="msoc-edge-0123456789abcdef",
        snapshot_digest="b" * 64,
        remaining_bytes=10,
    )
    assert session.charge(4).remaining_bytes == 6
    with pytest.raises(
        MacroSocietyArtifactError, match="macro_society_response_too_large"
    ):
        session.charge(11)


def test_publication_wraps_snapshot_and_payload() -> None:
    snapshot = _snapshot()
    publication = MacroSocietyPublication(
        snapshot=snapshot,
        payload=encode_macro_society_snapshot(snapshot),
        created_at_utc="2026-10-30T00:00:00Z",
    )
    assert publication.publication_id == snapshot.publication_id


def test_simulation_modules_do_not_import_outer_layers() -> None:
    forbidden = {
        "analysis",
        "experiments",
        "api",
        "persistence",
        "observer",
        "infrastructure",
    }
    for path in (ROOT / "src" / "simulation").glob("macro_society_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".", 1)[0] not in forbidden, path
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".", 1)[0] not in forbidden, path
