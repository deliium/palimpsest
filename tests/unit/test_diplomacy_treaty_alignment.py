# mypy: ignore-errors
"""V4-11 researcher-only treaty recollection alignment."""

from __future__ import annotations

import pytest

from analysis.diplomacy_alignment import (
    DiplomacyAlignmentStatus,
    classify_treaty_recollection_alignment,
)
from analysis.diplomacy_rows import (
    DiplomacyHarvestRows,
    DiplomacyTreatyRecollectionRow,
    DiplomacyTreatyRow,
    DiplomacyTreatyVersionRow,
)

pytestmark = pytest.mark.unit


def _version(*, digest: str = "a" * 64, subject: str = "ceasefire"):
    return DiplomacyTreatyVersionRow(
        owner_token="a" * 16,
        version_id="dpv-" + "0" * 16,
        treaty_id="dpg-" + "0" * 16,
        version_index=1,
        parent_version_ids=(),
        change_kind="original",
        party_tokens=("b" * 16, "c" * 16),
        provision_kinds=("non_hostility",),
        terms_digest=digest,
        record_refs=(),
        institutional_memory_refs=(),
        effective_tick=1,
        end_tick=None,
        proposer_party_token="b" * 16,
        proposer_envoy_token=None,
        provenance="communicated",
    )


def _recollection(
    *, digest: str | None, stance: str = "remember", subject: str = "ceasefire"
):
    return DiplomacyTreatyRecollectionRow(
        owner_token="a" * 16,
        treaty_ref="dpg-" + "0" * 16,
        version_ref="dpv-" + "0" * 16,
        subject_token=subject,
        basis="durable_record",
        stance=stance,
        claimed_terms_digest=digest,
        confidence=0.5,
        first_tick=1,
        last_tick=1,
        provenance="communicated",
    )


def _rows(recollection):
    return DiplomacyHarvestRows(
        treaties=(
            DiplomacyTreatyRow(
                owner_token="a" * 16,
                treaty_id="dpg-" + "0" * 16,
                relation_id="dpl-" + "0" * 16,
                party_tokens=("b" * 16, "c" * 16),
                subject_token="ceasefire",
                current_version_id="dpv-" + "0" * 16,
                opened_tick=1,
                last_tick=1,
                provenance="communicated",
            ),
        ),
        treaty_versions=(_version(),),
        treaty_recollections=(recollection,),
    )


def test_equal_digest_is_consistent() -> None:
    rows = classify_treaty_recollection_alignment(_rows(_recollection(digest="a" * 64)))
    assert rows[0].status == DiplomacyAlignmentStatus.CONSISTENT.value


def test_different_digest_is_inconsistent() -> None:
    rows = classify_treaty_recollection_alignment(_rows(_recollection(digest="b" * 64)))
    assert rows[0].status == DiplomacyAlignmentStatus.INCONSISTENT.value


def test_missing_claim_is_unresolved_or_not_applicable() -> None:
    remember = classify_treaty_recollection_alignment(_rows(_recollection(digest=None)))
    assert remember[0].status == DiplomacyAlignmentStatus.UNRESOLVED.value
    ignore = classify_treaty_recollection_alignment(
        _rows(_recollection(digest=None, stance="ignore"))
    )
    assert ignore[0].status == DiplomacyAlignmentStatus.NOT_APPLICABLE.value


def test_subject_mismatch_is_inconsistent() -> None:
    rows = classify_treaty_recollection_alignment(
        _rows(_recollection(digest="a" * 64, subject="trade"))
    )
    assert rows[0].status == DiplomacyAlignmentStatus.INCONSISTENT.value


def test_alignment_rows_have_no_truth_field() -> None:
    rows = classify_treaty_recollection_alignment(_rows(_recollection(digest="a" * 64)))
    assert not hasattr(rows[0], "truth")
    assert not hasattr(rows[0], "misremembered")
    assert not hasattr(rows[0], "guilty")
