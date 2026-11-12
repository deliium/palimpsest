"""V4-10 catalog append, value keys, and historical pin preservation."""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    all_metric_specifications,
    metric_specification,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]

CONTACT_KEYS = (
    "relation_count",
    "party_count",
    "contact_count",
    "envoy_count",
    "negotiation_count",
    "party_kind_histogram",
    "contact_kind_histogram",
    "envoy_status_histogram",
    "negotiation_status_histogram",
    "coverage",
)
INSTRUMENT_KEYS = (
    "instrument_count",
    "proposal_count",
    "promise_count",
    "agreement_count",
    "dispute_count",
    "shared_project_count",
    "apparently_accepted_count",
    "rejected_count",
    "withdrawn_count",
    "unresolved_count",
    "superseded_count",
    "misrepresentation_count",
    "misrepresentation_kind_histogram",
    "declaration_count",
    "acceptance_ratio",
    "coverage",
)
ENVOY_KEYS = (
    "consistent_count",
    "unresolved_count",
    "inconsistent_count",
    "not_applicable_count",
    "aligned_declaration_count",
    "consistency_ratio",
    "inconsistency_ratio",
    "coverage",
)
LANE_KEYS = (
    "pair_count",
    "lane_pair_count_histogram",
    "agent_relationship_pair_count",
    "trade_pair_count",
    "conflict_pair_count",
    "agreement_pair_count",
    "narrative_pair_count",
    "institutional_interaction_pair_count",
    "pairs_with_any_lane",
    "pairs_with_multiple_lanes",
    "lane_coverage_ratio",
    "coverage",
)


def test_catalog_is_176_with_four_diplomacy_families_before_treaties() -> None:
    specs = all_metric_specifications()
    assert METRIC_FAMILY_COUNT == 216
    assert len(specs) == 216
    assert [spec.family_id for spec in specs[160:164]] == [
        MetricFamilyId.DIPLOMATIC_CONTACT_STRUCTURE,
        MetricFamilyId.DIPLOMATIC_INSTRUMENT_OUTCOMES,
        MetricFamilyId.DIPLOMATIC_ENVOY_ALIGNMENT,
        MetricFamilyId.INTER_SOCIETY_RELATION_LANES,
    ]
    assert [spec.family_id for spec in specs[164:168]] == [
        MetricFamilyId.TREATY_STRUCTURE,
        MetricFamilyId.TREATY_VERSION_LINEAGE,
        MetricFamilyId.TREATY_RECOLLECTION,
        MetricFamilyId.TREATY_ANCHOR_COVERAGE,
    ]
    assert len({spec.family_id for spec in specs}) == 216


def test_diplomacy_value_keys_are_exact() -> None:
    assert (
        tuple(
            metric_specification(MetricFamilyId.DIPLOMATIC_CONTACT_STRUCTURE).value_keys
        )
        == CONTACT_KEYS
    )
    assert (
        tuple(
            metric_specification(
                MetricFamilyId.DIPLOMATIC_INSTRUMENT_OUTCOMES
            ).value_keys
        )
        == INSTRUMENT_KEYS
    )
    assert (
        tuple(
            metric_specification(MetricFamilyId.DIPLOMATIC_ENVOY_ALIGNMENT).value_keys
        )
        == ENVOY_KEYS
    )
    assert (
        tuple(
            metric_specification(MetricFamilyId.INTER_SOCIETY_RELATION_LANES).value_keys
        )
        == LANE_KEYS
    )


def test_no_score_or_composite_key_exists() -> None:
    forbidden = {
        "score",
        "relation_score",
        "trust",
        "rank",
        "valence",
        "index",
        "composite",
        "overall_relation",
        "bilateral_score",
        "mean_score",
    }
    for spec in all_metric_specifications()[-4:]:
        assert forbidden.isdisjoint(spec.value_keys)


def test_historical_revision_pins_are_preserved() -> None:
    architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    assert "families (157 -> 160)" in architecture
    delegation = (ROOT / "docs" / "delegation-representation.md").read_text(
        encoding="utf-8"
    )
    assert "raising the count from 157 to **160**" in delegation
    evidence = (ROOT / "docs" / "evidence-testimony.md").read_text(encoding="utf-8")
    assert "154 to 157" in evidence
