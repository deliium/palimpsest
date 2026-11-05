# mypy: ignore-errors
"""V4-11 treaty paging is bounded, sorted, and snapshot-pure."""

from __future__ import annotations

from dataclasses import replace

import pytest

from simulation.diplomacy_models import (
    DiplomacySnapshot,
    DiplomacySnapshotPartyRow,
    DiplomacySnapshotTreatyRow,
    DiplomacySnapshotTreatyVersionRow,
    empty_diplomacy_snapshot,
)
from simulation.diplomacy_paging import (
    select_diplomacy_treaties,
    select_diplomacy_treaty,
    select_diplomacy_treaty_versions,
)

pytestmark = pytest.mark.unit


def _snapshot() -> DiplomacySnapshot:
    base = empty_diplomacy_snapshot("run-1", revision="rev-1", window_end=4)
    rows = tuple(
        DiplomacySnapshotTreatyRow(
            treaty_id=f"dpg-{index:016x}",
            relation_id="dpl-" + "0" * 16,
            owner_token="a" * 16,
            party_tokens=("a" * 16, "b" * 16),
            subject_kind="ceasefire",
            current_version_id=f"dpv-{index:016x}",
            status="proposed",
            opened_tick=index,
            last_tick=index,
            provenance="communicated",
        )
        for index in range(5)
    )
    versions = tuple(
        DiplomacySnapshotTreatyVersionRow(
            version_id=f"dpv-{index:016x}",
            treaty_id=f"dpg-{index:016x}",
            owner_token="a" * 16,
            version_index=1,
            parent_version_ids=(),
            change_kind="original",
            status="proposed",
            acceptance_basis="none",
            party_tokens=("a" * 16, "b" * 16),
            provision_kinds=("non_hostility",),
            terms_digest=f"{index:064x}",
            record_refs=(),
            institutional_memory_refs=(),
            effective_tick=index,
            end_tick=None,
            proposer_party_token="a" * 16,
            proposer_envoy_token=None,
            provenance="communicated",
        )
        for index in range(5)
    )
    return DiplomacySnapshot(
        run_id=base.run_id,
        created_revision=base.created_revision,
        window_end=base.window_end,
        policy_version=base.policy_version,
        schema_version=base.schema_version,
        parties=(
            DiplomacySnapshotPartyRow(
                party_id="dpp-" + "0" * 16,
                owner_token="a" * 16,
                party_token="a" * 16,
                party_kind="agent",
                resolution="resolved",
                first_seen_tick=0,
                provenance="self_declared",
            ),
            DiplomacySnapshotPartyRow(
                party_id="dpp-" + "1" * 16,
                owner_token="a" * 16,
                party_token="b" * 16,
                party_kind="agent",
                resolution="resolved",
                first_seen_tick=0,
                provenance="communicated",
            ),
        ),
        treaties=rows,
        treaty_versions=versions,
    )


def test_treaties_page_is_sorted_and_clamped() -> None:
    snapshot = _snapshot()
    page = select_diplomacy_treaties(snapshot, limit=2)
    assert len(page.rows) == 2
    assert page.next_key is not None
    assert snapshot.treaties == _snapshot().treaties


def test_treaty_page_orders_by_opened_tick_then_id() -> None:
    base = _snapshot()
    low_id_high_tick = replace(
        base.treaties[0],
        treaty_id="dpg-" + f"{1:016x}",
        current_version_id="dpv-" + f"{1:016x}",
        opened_tick=2,
        last_tick=2,
    )
    high_id_low_tick = replace(
        base.treaties[1],
        treaty_id="dpg-" + f"{2:016x}",
        current_version_id="dpv-" + f"{2:016x}",
        opened_tick=1,
        last_tick=1,
    )
    low_version = replace(
        base.treaty_versions[1],
        version_id="dpv-" + f"{2:016x}",
        treaty_id="dpg-" + f"{2:016x}",
        effective_tick=1,
    )
    high_version = replace(
        base.treaty_versions[0],
        version_id="dpv-" + f"{1:016x}",
        treaty_id="dpg-" + f"{1:016x}",
        effective_tick=2,
    )
    snapshot = replace(
        base,
        treaties=(high_id_low_tick, low_id_high_tick),
        treaty_versions=(low_version, high_version),
    )
    page = select_diplomacy_treaties(snapshot)
    assert [row.opened_tick for row in page.rows] == [1, 2]


def test_treaty_detail_is_bounded() -> None:
    snapshot = _snapshot()
    detail = select_diplomacy_treaty(
        snapshot, snapshot.treaties[0].treaty_id, limit=500
    )
    assert detail.rows[0] == snapshot.treaties[0]
    assert detail.truncated is False


def test_version_page_filters_by_treaty() -> None:
    snapshot = _snapshot()
    page = select_diplomacy_treaty_versions(
        snapshot, treaty_id=snapshot.treaties[0].treaty_id
    )
    assert len(page.rows) == 1
    assert page.rows[0].treaty_id == snapshot.treaties[0].treaty_id
