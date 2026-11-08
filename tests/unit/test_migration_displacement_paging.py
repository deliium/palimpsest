# mypy: ignore-errors
"""Migration-displacement cursors, fingerprints, and bounded paging."""

from __future__ import annotations

import pytest

from simulation.migration_displacement_models import (
    MIGRATION_DISPLACEMENT_SNAPSHOT_POLICY,
    MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION,
    MigrationCauseSnapshotRow,
    MigrationDisplacementSnapshot,
    MigrationDisplacementSummaryRow,
    MigrationOutcomeSnapshotRow,
    MigrationRouteSnapshotRow,
    MigrationWaveSnapshotRow,
    empty_migration_displacement_snapshot,
)
from simulation.migration_displacement_paging import (
    MAX_PAGE_LIMIT,
    MigrationRowSelection,
    page_migration_detail,
    page_migration_rows,
)
from simulation.migration_displacement_ports import (
    MIGRATION_DISPLACEMENT_CURSOR_PURPOSES,
    MigrationDisplacementCursor,
    bounded_migration_detail_rows,
    migration_displacement_cursor_matches,
    migration_displacement_query_fingerprint,
)

DIGEST = "a" * 64


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


def test_six_cursor_purposes_exist() -> None:
    assert MIGRATION_DISPLACEMENT_CURSOR_PURPOSES == (
        "summary",
        "waves",
        "wave",
        "routes",
        "causes",
        "outcomes",
    )
    assert MAX_PAGE_LIMIT == 500


def test_page_limit_is_bounded() -> None:
    empty = empty_migration_displacement_snapshot(
        "run-1", digest=DIGEST, publication_id="md-pub-" + ("c" * 32)
    )
    with pytest.raises(ValueError, match="migration_displacement_page_limit"):
        page_migration_rows(
            empty,
            MigrationRowSelection(purpose="waves", after_key=None, limit=0),
        )
    with pytest.raises(ValueError, match="migration_displacement_page_limit"):
        page_migration_rows(
            empty,
            MigrationRowSelection(purpose="waves", after_key=None, limit=501),
        )
    with pytest.raises(ValueError, match="migration_displacement_page_limit"):
        MigrationDisplacementCursor(
            purpose="waves",
            after_key=None,
            limit=501,
            fingerprint="a" * 64,
        )


def test_rows_are_sorted_by_stable_keys() -> None:
    waves = (
        MigrationWaveSnapshotRow(
            "mdw-b",
            "mdl-a",
            "mdl-b",
            ("mdo-1", "mdo-2"),
            ("mdl-a", "mdl-b"),
            2,
            3,
            (),
            "unknown",
            (),
            0,
            (),
            "complete",
        ),
        MigrationWaveSnapshotRow(
            "mdw-a",
            "mdl-a",
            "mdl-b",
            ("mdo-1", "mdo-2"),
            ("mdl-a", "mdl-b"),
            1,
            2,
            (),
            "unknown",
            (),
            0,
            (),
            "complete",
        ),
    )
    # Snapshot construction requires waves sorted already.
    ordered_waves = tuple(sorted(waves, key=lambda row: (row.start_tick, row.wave_token)))
    snapshot = _snapshot(
        waves=ordered_waves,
        summary=_summary(wave_count=2, unknown_count=2),
    )
    page = page_migration_rows(
        snapshot,
        MigrationRowSelection(purpose="waves", after_key=None, limit=10),
    )
    assert [row.wave_token for row in page.rows] == ["mdw-a", "mdw-b"]


def test_cursor_binds_run_publication_digest_purpose_filters_and_limit() -> None:
    base = dict(
        run_id="run-1",
        publication_id="md-pub-1",
        digest=DIGEST,
        purpose="waves",
        filters={"layer": "all"},
        after_key=None,
        limit=10,
    )
    fingerprint = migration_displacement_query_fingerprint(**base)
    assert len(fingerprint) == 64
    cursor = MigrationDisplacementCursor(
        purpose="waves",
        after_key=None,
        limit=10,
        fingerprint=fingerprint,
    )
    assert migration_displacement_cursor_matches(cursor, fingerprint)


def test_changed_binding_does_not_match() -> None:
    base = dict(
        run_id="run-1",
        publication_id="md-pub-1",
        digest=DIGEST,
        purpose="causes",
        filters={"owner": "mown-1"},
        after_key="a",
        limit=25,
    )
    fingerprint = migration_displacement_query_fingerprint(**base)
    cursor = MigrationDisplacementCursor(
        purpose="causes",
        after_key="a",
        limit=25,
        fingerprint=fingerprint,
    )
    for change in (
        {"run_id": "run-2"},
        {"publication_id": "md-pub-2"},
        {"digest": "b" * 64},
        {"purpose": "routes"},
        {"filters": {"owner": "mown-2"}},
        {"after_key": "b"},
        {"limit": 26},
    ):
        values = dict(base)
        values.update(change)
        assert migration_displacement_query_fingerprint(**values) != fingerprint
        assert not migration_displacement_cursor_matches(
            cursor, migration_displacement_query_fingerprint(**values)
        )


def test_detail_lookup_returns_none_for_unknown_token() -> None:
    wave = MigrationWaveSnapshotRow(
        "mdw-1",
        "mdl-a",
        "mdl-b",
        ("mdo-1", "mdo-2"),
        ("mdl-a", "mdl-b"),
        0,
        1,
        (),
        "unknown",
        (),
        0,
        (),
        "complete",
    )
    snapshot = _snapshot(
        waves=(wave,),
        summary=_summary(wave_count=1, unknown_count=1),
    )
    assert page_migration_detail(snapshot, "wave", "mdw-1") is wave
    assert page_migration_detail(snapshot, "wave", "mdw-missing") is None
    assert bounded_migration_detail_rows(snapshot, "wave", "mdw-missing", 1) is None


def test_paging_never_reorders_a_published_snapshot() -> None:
    routes = (
        MigrationRouteSnapshotRow(
            "mown-1",
            "mdr-a",
            "mdl-a",
            "mdl-b",
            ("mdl-a", "mdl-b"),
            1,
            0.0,
            "direct_observation",
            "open",
            0,
            1,
        ),
        MigrationRouteSnapshotRow(
            "mown-1",
            "mdr-b",
            "mdl-a",
            "mdl-c",
            ("mdl-a", "mdl-c"),
            1,
            0.0,
            "direct_observation",
            "open",
            1,
            2,
        ),
    )
    causes = (
        MigrationCauseSnapshotRow(
            "mown-1",
            "mdc-a",
            "conflict",
            "direct_observation",
            "",
            0.5,
            0,
            "active",
        ),
        MigrationCauseSnapshotRow(
            "mown-1",
            "mdc-b",
            "opportunity",
            "inference",
            "",
            0.4,
            1,
            "active",
        ),
    )
    outcomes = (
        MigrationOutcomeSnapshotRow(
            "mdn-a",
            "mdo-1",
            "mdl-b",
            3,
            1,
            0,
            0,
            0,
            "settled",
            "complete",
            False,
        ),
        MigrationOutcomeSnapshotRow(
            "mdn-b",
            "mdo-2",
            "mdl-b",
            1,
            0,
            0,
            0,
            0,
            "transient",
            "partial",
            True,
        ),
    )
    snapshot = _snapshot(
        routes=routes,
        causes=causes,
        outcomes=outcomes,
        summary=_summary(
            cause_count=2,
            integration_settled_count=1,
            integration_transient_count=1,
            outcome_count=2,
        ),
    )
    published_routes = snapshot.routes
    first = page_migration_rows(
        snapshot,
        MigrationRowSelection(purpose="routes", after_key=None, limit=1),
    )
    second = page_migration_rows(
        snapshot,
        MigrationRowSelection(
            purpose="routes", after_key=first.next_key, limit=1
        ),
    )
    assert snapshot.routes is published_routes
    assert [row.route_token for row in first.rows + second.rows] == ["mdr-a", "mdr-b"]
    assert second.next_key is None
    cause_page = page_migration_rows(
        snapshot,
        MigrationRowSelection(purpose="causes", after_key=None, limit=10),
    )
    assert [row.cause_token for row in cause_page.rows] == ["mdc-a", "mdc-b"]
    outcome_page = page_migration_rows(
        snapshot,
        MigrationRowSelection(purpose="outcomes", after_key=None, limit=10),
    )
    assert [row.outcome_token for row in outcome_page.rows] == ["mdn-a", "mdn-b"]
