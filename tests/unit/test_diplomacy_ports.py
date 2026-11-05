"""V4-10 diplomacy paging and cursor-bound ports."""

from __future__ import annotations

from typing import Any, cast

import pytest

from simulation.diplomacy_models import (
    DIPLOMACY_CURSOR_PURPOSES,
    DiplomacyArtifactError,
    DiplomacySnapshot,
    DiplomacySnapshotContactRow,
    DiplomacySnapshotPartyRow,
    DiplomacySnapshotRelationRow,
    empty_diplomacy_snapshot,
)
from simulation.diplomacy_paging import (
    select_diplomacy_instrument,
    select_diplomacy_relation,
    select_diplomacy_relations,
)
from simulation.diplomacy_ports import (
    DiplomacyCursor,
    DiplomacyPortError,
    bounded_detail_rows,
    diplomacy_cursor_matches,
    diplomacy_query_fingerprint,
)

pytestmark = pytest.mark.unit

OWNER = "0" * 16
OTHER = "1" * 16


def _relation(index: int) -> DiplomacySnapshotRelationRow:
    return DiplomacySnapshotRelationRow(
        relation_id="dpl-" + f"{index:016x}",
        owner_token=OWNER,
        party_tokens=(OWNER, OTHER),
        opened_tick=index,
        last_tick=index,
        provenance="communicated",
    )


def _party(index: int) -> DiplomacySnapshotPartyRow:
    return DiplomacySnapshotPartyRow(
        party_id="dpp-" + f"{index:016x}",
        owner_token=OWNER,
        party_token=OWNER if index == 0 else OTHER,
        party_kind="agent",
        resolution="resolved",
        first_seen_tick=0,
        provenance="communicated",
    )


def _snapshot() -> DiplomacySnapshot:
    return DiplomacySnapshot(
        run_id="run-1",
        created_revision="rev-1",
        window_end=3,
        relations=tuple(_relation(index) for index in range(1, 4)),
        parties=(_party(0), _party(1)),
        contacts=tuple(
            DiplomacySnapshotContactRow(
                contact_id="dpc-" + f"{index:016x}",
                relation_id="dpl-" + f"{1:016x}",
                owner_token=OWNER,
                tick=index,
                contact_kind="direct_co_presence",
                location_anchor="region-1",
                participant_count=2,
                provenance="witnessed_contact",
            )
            for index in range(1, 4)
        ),
    )


def test_cursor_purposes_are_exactly_eight() -> None:
    assert DIPLOMACY_CURSOR_PURPOSES == (
        "summary",
        "relations",
        "relation",
        "instruments",
        "instrument",
        "lineage",
        "treaties",
        "treaty",
    )


def test_paging_is_bounded_and_stable() -> None:
    snapshot = _snapshot()
    first = select_diplomacy_relations(snapshot, limit=1)
    assert len(first.rows) == 1
    assert first.next_key == cast(Any, first.rows[0]).relation_id
    second = select_diplomacy_relations(snapshot, after_key=first.next_key, limit=1)
    assert len(second.rows) == 1
    assert cast(Any, second.rows[0]).relation_id != cast(Any, first.rows[0]).relation_id
    assert len(select_diplomacy_relations(snapshot, limit=0).rows) == 1
    assert len(select_diplomacy_relations(snapshot, limit=501).rows) == 3
    assert (
        select_diplomacy_relations(
            empty_diplomacy_snapshot("run-1", revision="rev-1", window_end=0)
        ).rows
        == ()
    )


def test_relation_and_instrument_detail_are_bounded() -> None:
    snapshot = _snapshot()
    detail = select_diplomacy_relation(snapshot, snapshot.relations[0].relation_id)
    assert detail.rows
    truncated = select_diplomacy_relation(
        snapshot, snapshot.relations[0].relation_id, limit=1
    )
    assert truncated.truncated
    with pytest.raises(DiplomacyArtifactError):
        select_diplomacy_relation(snapshot, "dpl-" + "f" * 16)
    with pytest.raises(DiplomacyArtifactError):
        select_diplomacy_instrument(snapshot, "dpi-" + "f" * 16)


def test_fingerprint_binds_every_input() -> None:
    base = diplomacy_query_fingerprint(
        run_id="run-1",
        publication_id="dip-pub-1",
        snapshot_digest="a" * 64,
        purpose="relations",
        filters={"kind": "proposal"},
    )
    for change in (
        {"run_id": "run-2"},
        {"publication_id": "dip-pub-2"},
        {"snapshot_digest": "b" * 64},
        {"purpose": "instruments"},
        {"filters": {"kind": "agreement"}},
    ):
        values = {
            "run_id": "run-1",
            "publication_id": "dip-pub-1",
            "snapshot_digest": "a" * 64,
            "purpose": "relations",
            "filters": {"kind": "proposal"},
        }
        values.update(change)
        assert (
            diplomacy_query_fingerprint(**values)  # type: ignore[arg-type]
            != base
        )


def test_cursor_mismatch_is_false() -> None:
    cursor = DiplomacyCursor(
        run_id="run-1",
        publication_id="dip-pub-1",
        snapshot_digest="a" * 64,
        purpose="relations",
        filters=(("kind", "proposal"),),
    )
    assert diplomacy_cursor_matches(
        cursor,
        run_id="run-1",
        publication_id="dip-pub-1",
        snapshot_digest="a" * 64,
        purpose="relations",
        filters={"kind": "proposal"},
    )
    assert not diplomacy_cursor_matches(
        cursor,
        run_id="run-2",
        publication_id="dip-pub-1",
        snapshot_digest="a" * 64,
        purpose="relations",
        filters={"kind": "proposal"},
    )
    with pytest.raises(DiplomacyPortError):
        DiplomacyCursor(
            run_id="run-1",
            publication_id="dip-pub-1",
            snapshot_digest="a" * 64,
            purpose="unknown",
            filters=(),
        )


def test_detail_rows_truncate() -> None:
    rows = tuple(range(600))
    clipped, truncated = bounded_detail_rows(rows)
    assert len(clipped) == 500
    assert truncated
    assert bounded_detail_rows((1, 2)) == ((1, 2), False)
