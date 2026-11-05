# mypy: ignore-errors
"""V4-11 four treaty metric documents."""

from __future__ import annotations

from dataclasses import replace

import pytest

from analysis.diplomacy_alignment import (
    TreatyRecollectionAlignmentRow,
)
from analysis.diplomacy_contract import DiplomacyCoverage
from analysis.diplomacy_metrics import (
    compute_treaty_anchor_coverage,
    compute_treaty_recollection,
    compute_treaty_structure,
    compute_treaty_version_lineage,
)
from analysis.diplomacy_rows import (
    DiplomacyHarvestRows,
    DiplomacyTerminationRow,
    DiplomacyTreatyAnchorRow,
    DiplomacyTreatyDeclarationRow,
    DiplomacyTreatyLineageRow,
    DiplomacyTreatyRecollectionRow,
    DiplomacyTreatyRow,
    DiplomacyTreatyVersionRow,
)
from analysis.specifications import MetricFamilyId, metric_specification

pytestmark = pytest.mark.unit

RUN = "run-treaty"
REV = "rev-treaty"


def _rows() -> DiplomacyHarvestRows:
    return DiplomacyHarvestRows(
        treaties=(
            DiplomacyTreatyRow(
                owner_token="a" * 16,
                treaty_id="dpg-" + "0" * 16,
                relation_id="dpl-" + "0" * 16,
                party_tokens=("b" * 16, "c" * 16),
                subject_token="ceasefire",
                current_version_id="dpv-" + "1" * 16,
                opened_tick=1,
                last_tick=2,
                provenance="communicated",
            ),
        ),
        treaty_versions=(
            DiplomacyTreatyVersionRow(
                owner_token="a" * 16,
                version_id="dpv-" + "0" * 16,
                treaty_id="dpg-" + "0" * 16,
                version_index=1,
                parent_version_ids=(),
                change_kind="original",
                party_tokens=("b" * 16, "c" * 16),
                provision_kinds=("non_hostility",),
                terms_digest="a" * 64,
                record_refs=("record-1",),
                institutional_memory_refs=(),
                effective_tick=1,
                end_tick=None,
                proposer_party_token="b" * 16,
                proposer_envoy_token=None,
                provenance="communicated",
            ),
            DiplomacyTreatyVersionRow(
                owner_token="a" * 16,
                version_id="dpv-" + "1" * 16,
                treaty_id="dpg-" + "0" * 16,
                version_index=2,
                parent_version_ids=("dpv-" + "0" * 16,),
                change_kind="renewal",
                party_tokens=("b" * 16, "c" * 16),
                provision_kinds=("non_hostility",),
                terms_digest="b" * 64,
                record_refs=(),
                institutional_memory_refs=("d" * 64,),
                effective_tick=2,
                end_tick=None,
                proposer_party_token="b" * 16,
                proposer_envoy_token=None,
                provenance="communicated",
            ),
        ),
        treaty_declarations=(
            DiplomacyTreatyDeclarationRow(
                owner_token="a" * 16,
                treaty_id="dpg-" + "0" * 16,
                version_id="dpv-" + "0" * 16,
                party_token="b" * 16,
                envoy_token=None,
                act="accept",
                declared_tick=2,
                provenance="communicated",
            ),
            DiplomacyTreatyDeclarationRow(
                owner_token="a" * 16,
                treaty_id="dpg-" + "0" * 16,
                version_id="dpv-" + "0" * 16,
                party_token="c" * 16,
                envoy_token=None,
                act="accept",
                declared_tick=2,
                provenance="communicated",
            ),
        ),
        treaty_recollections=(
            DiplomacyTreatyRecollectionRow(
                owner_token="a" * 16,
                treaty_ref="dpg-" + "0" * 16,
                version_ref="dpv-" + "0" * 16,
                subject_token="ceasefire",
                basis="durable_record",
                stance="remember",
                claimed_terms_digest="a" * 64,
                confidence=0.5,
                first_tick=2,
                last_tick=2,
                provenance="communicated",
            ),
        ),
        treaty_anchors=(
            DiplomacyTreatyAnchorRow(
                owner_token="a" * 16,
                version_id="dpv-" + "0" * 16,
                record_anchor_count=1,
                institutional_memory_anchor_count=0,
                has_record_anchor=True,
                has_institutional_memory_anchor=False,
                has_any_anchor=True,
            ),
            DiplomacyTreatyAnchorRow(
                owner_token="a" * 16,
                version_id="dpv-" + "1" * 16,
                record_anchor_count=0,
                institutional_memory_anchor_count=1,
                has_record_anchor=False,
                has_institutional_memory_anchor=True,
                has_any_anchor=True,
            ),
        ),
        treaty_lineage=(
            DiplomacyTreatyLineageRow(
                owner_token="a" * 16,
                treaty_id="dpg-" + "0" * 16,
                parent_version_id="dpv-" + "0" * 16,
                child_version_id="dpv-" + "1" * 16,
                change_kind="renewal",
                tick=2,
            ),
        ),
        coverage=DiplomacyCoverage.COMPLETE,
    )


@pytest.mark.parametrize(
    ("family", "compute", "keys"),
    (
        (
            MetricFamilyId.TREATY_STRUCTURE,
            compute_treaty_structure,
            (
                "treaty_count",
                "participant_count",
                "multi_party_count",
                "apparently_accepted_count",
                "suspended_count",
                "terminated_count",
                "expired_count",
                "superseded_count",
                "subject_kind_histogram",
                "participant_count_histogram",
                "coverage",
            ),
        ),
        (
            MetricFamilyId.TREATY_VERSION_LINEAGE,
            compute_treaty_version_lineage,
            (
                "version_count",
                "original_count",
                "amendment_count",
                "renewal_count",
                "accession_count",
                "withdrawal_count",
                "suspension_count",
                "termination_count",
                "lineage_edge_count",
                "max_lineage_depth",
                "renewal_ratio",
                "coverage",
            ),
        ),
        (
            MetricFamilyId.TREATY_RECOLLECTION,
            None,
            (
                "recollection_count",
                "remember_count",
                "reinterpret_count",
                "ignore_count",
                "renew_count",
                "basis_histogram",
                "consistent_count",
                "unresolved_count",
                "inconsistent_count",
                "not_applicable_count",
                "aligned_recollection_count",
                "consistency_ratio",
                "inconsistency_ratio",
                "coverage",
            ),
        ),
        (
            MetricFamilyId.TREATY_ANCHOR_COVERAGE,
            compute_treaty_anchor_coverage,
            (
                "version_count",
                "record_anchor_count",
                "institutional_memory_anchor_count",
                "versions_with_record_anchor",
                "versions_with_institutional_memory_anchor",
                "versions_without_any_anchor",
                "record_anchor_coverage_ratio",
                "institutional_memory_coverage_ratio",
                "coverage",
            ),
        ),
    ),
)
def test_value_keys_are_exact(family, compute, keys) -> None:
    assert tuple(metric_specification(family).value_keys) == keys


def test_absent_input_is_absent() -> None:
    document = compute_treaty_structure(None, run_id=RUN, input_revision=REV)
    assert document.availability.value == "absent"
    assert document.values == {}


def test_compute_documents_have_expected_counts() -> None:
    rows = _rows()
    structure = compute_treaty_structure(rows, run_id=RUN, input_revision=REV)
    assert structure.values["treaty_count"] == 1
    assert structure.values["apparently_accepted_count"] == 1
    lineage = compute_treaty_version_lineage(rows, run_id=RUN, input_revision=REV)
    assert lineage.values["version_count"] == 2
    assert lineage.values["renewal_count"] == 1
    assert lineage.values["lineage_edge_count"] == 1
    alignment = (
        TreatyRecollectionAlignmentRow(
            owner_token="a" * 16,
            treaty_ref="dpg-" + "0" * 16,
            version_ref="dpv-" + "0" * 16,
            subject_token="ceasefire",
            claimed_terms_digest="a" * 64,
            status="consistent",
            basis="durable_record",
        ),
    )
    recollection = compute_treaty_recollection(
        rows, alignment, run_id=RUN, input_revision=REV
    )
    assert recollection.values["consistent_count"] == 1
    anchors = compute_treaty_anchor_coverage(rows, run_id=RUN, input_revision=REV)
    assert anchors.values["version_count"] == 2
    assert anchors.values["versions_without_any_anchor"] == 0


def test_partial_three_party_acceptance_is_not_counted_as_accepted() -> None:
    rows = _rows()
    version = replace(
        rows.treaty_versions[0],
        party_tokens=("a" * 16, "b" * 16, "c" * 16),
    )
    partial = replace(rows, treaty_versions=(version,))
    assert (
        compute_treaty_structure(partial, run_id=RUN, input_revision=REV).values[
            "apparently_accepted_count"
        ]
        == 0
    )


def test_acceptance_and_terminal_counts_use_retained_rows() -> None:
    rows = _rows()
    one_accept = replace(rows, treaty_declarations=rows.treaty_declarations[:1])
    assert (
        compute_treaty_structure(
            one_accept, run_id=RUN, input_revision=REV
        ).values["apparently_accepted_count"]
        == 0
    )
    terminations = (
        DiplomacyTerminationRow(
            owner_token="a" * 16,
            target_kind="treaty_version",
            kind="expired",
            tick=3,
            target_ref="dpv-" + "0" * 16,
        ),
        DiplomacyTerminationRow(
            owner_token="a" * 16,
            target_kind="treaty_version",
            kind="superseded",
            tick=4,
            target_ref="dpv-" + "1" * 16,
        ),
    )
    with_terminations = replace(rows, terminations=terminations)
    structure = compute_treaty_structure(
        with_terminations, run_id=RUN, input_revision=REV
    )
    assert structure.values["expired_count"] == 1
    assert structure.values["superseded_count"] == 1


def test_no_forbidden_metric_keys_exist() -> None:
    forbidden = {
        "score",
        "relation_score",
        "trust",
        "rank",
        "valence",
        "index",
        "composite",
        "mean_score",
        "overall_relation",
        "truth",
        "verified",
        "legitimate",
    }
    for family in (
        MetricFamilyId.TREATY_STRUCTURE,
        MetricFamilyId.TREATY_VERSION_LINEAGE,
        MetricFamilyId.TREATY_RECOLLECTION,
        MetricFamilyId.TREATY_ANCHOR_COVERAGE,
    ):
        assert forbidden.isdisjoint(metric_specification(family).value_keys)
