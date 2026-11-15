# mypy: ignore-errors
"""Eight social-mobility metric documents and their state mapping."""

from __future__ import annotations

import pytest

from analysis.models import MetricAvailability
from analysis.social_mobility_analysis import (
    empty_social_mobility_analysis,
    harvest_social_mobility_analysis,
)
from analysis.social_mobility_contract import (
    SocialMobilityCoverage,
    SocialMobilityDomain,
    SocialMobilityLayer,
    SocialMobilityMeasure,
    social_mobility_lineage_token,
    social_mobility_owner_token,
)
from analysis.social_mobility_genealogy import SocialMobilityGenealogyHarvest
from analysis.social_mobility_metrics import (
    compute_educational_access_mobility,
    compute_organization_role_mobility,
    compute_productive_asset_mobility,
    compute_resource_mobility,
    compute_skill_mobility,
    compute_social_influence_mobility,
    compute_social_mobility_coverage,
    compute_social_mobility_generation_lag,
)
from analysis.social_mobility_outcomes import SocialMobilityOutcomeHarvest
from analysis.social_mobility_rows import (
    SocialMobilityGenealogyRow,
    SocialMobilityLineageEntry,
    SocialMobilityOutcomeRow,
)

pytestmark = pytest.mark.unit

_DOMAIN_FUNCTIONS = (
    (compute_resource_mobility, "resource_mobility"),
    (compute_skill_mobility, "skill_mobility"),
    (compute_social_influence_mobility, "social_influence_mobility"),
    (compute_organization_role_mobility, "organization_role_mobility"),
    (compute_educational_access_mobility, "educational_access_mobility"),
    (compute_productive_asset_mobility, "productive_asset_mobility"),
    (compute_social_mobility_generation_lag, "social_mobility_generation_lag"),
    (compute_social_mobility_coverage, "social_mobility_coverage"),
)


def _token(name: str) -> str:
    return social_mobility_owner_token(name)


def _analysis():
    lineages = []
    edges = []
    generations = {}
    rows = []
    for index in range(8):
        ancestor = f"entity:a{index}"
        descendant = f"entity:b{index}"
        lineages.append(
            SocialMobilityLineageEntry(
                lineage_token=social_mobility_lineage_token(
                    _token(ancestor), _token(descendant)
                ),
                ancestor_token=_token(ancestor),
                descendant_token=_token(descendant),
                generation_lag=1,
                ancestor_generation=0,
                descendant_generation=1,
            )
        )
        edges.append(
            SocialMobilityGenealogyRow(
                parent_token=_token(ancestor),
                child_token=_token(descendant),
                parent_generation=0,
                child_generation=1,
                established_tick=index,
                window_index=0,
            )
        )
        generations[_token(ancestor)] = 0
        generations[_token(descendant)] = 1
        rows.append(
            SocialMobilityOutcomeRow(
                owner_token=_token(ancestor),
                generation_index=0,
                tick=31,
                window_index=0,
                domain=SocialMobilityDomain.RESOURCES,
                measure=SocialMobilityMeasure.OBSERVED_RESOURCE_ITEM_COUNT,
                quantity=index,
                layer=SocialMobilityLayer.OBJECTIVE_OUTCOME,
            )
        )
        rows.append(
            SocialMobilityOutcomeRow(
                owner_token=_token(descendant),
                generation_index=1,
                tick=31,
                window_index=0,
                domain=SocialMobilityDomain.RESOURCES,
                measure=SocialMobilityMeasure.OBSERVED_RESOURCE_ITEM_COUNT,
                quantity=index + 1,
                layer=SocialMobilityLayer.OBJECTIVE_OUTCOME,
            )
        )
    genealogy = SocialMobilityGenealogyHarvest(
        edges=tuple(edges),
        generations=tuple(sorted(generations.items())),
        lineages=tuple(lineages),
        coverage=SocialMobilityCoverage.COMPLETE,
        event_count=8,
        owner_count=16,
        max_generation_index=1,
    )
    outcomes = SocialMobilityOutcomeHarvest(
        rows=tuple(rows),
        coverage=SocialMobilityCoverage.COMPLETE,
        event_count=16,
        owner_count=16,
    )
    return harvest_social_mobility_analysis(genealogy=genealogy, outcomes=outcomes)


def test_eight_documents_are_emitted_with_the_expected_family_ids() -> None:
    analysis = _analysis()
    for function, family in _DOMAIN_FUNCTIONS:
        document = function(analysis, run_id="run:1", input_revision="rev:1")
        assert document.metric_family == family
        assert document.run_id == "run:1"


def test_resource_document_reports_domain_statistics() -> None:
    document = compute_resource_mobility(
        _analysis(), run_id="run:1", input_revision="rev:1"
    )
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["pair_count"] == 8
    assert document.values["resolved_pair_count"] == 8
    assert document.values["persistence_direction"] in {"persistent", "mobile"}
    assert -1_000 <= document.values["rank_correlation_milli"] <= 1_000
    assert document.values["coverage"] == "complete"
    assert "score" not in document.values
    assert "class" not in document.values


def test_missing_domains_are_unknown_not_zero_filled() -> None:
    analysis = _analysis()
    document = compute_skill_mobility(analysis, run_id="run:1", input_revision="rev:1")
    assert document.availability is MetricAvailability.UNKNOWN
    assert document.values == {}
    assert document.coverage.observed == 0


def test_generation_lag_document_has_four_lag_strata() -> None:
    document = compute_social_mobility_generation_lag(
        _analysis(), run_id="run:1", input_revision="rev:1"
    )
    for lag in range(1, 5):
        assert f"lag{lag}_pair_count" in document.values
        assert f"lag{lag}_same_bin_share_milli" in document.values
    assert document.values["lag1_pair_count"] == 8


def test_coverage_document_reports_all_row_families() -> None:
    document = compute_social_mobility_coverage(
        _analysis(), run_id="run:1", input_revision="rev:1"
    )
    for key in (
        "generation_count",
        "owner_count",
        "genealogy_edge_count",
        "pair_count",
        "resolved_pair_count",
        "unresolved_pair_count",
        "domain_available_count",
        "truncated",
    ):
        assert key in document.values
    assert document.values["truncated"] is True


def test_empty_analysis_yields_unknown_documents() -> None:
    empty = empty_social_mobility_analysis()
    for function, _ in _DOMAIN_FUNCTIONS:
        document = function(empty, run_id="run:1", input_revision="rev:1")
        assert document.availability is MetricAvailability.UNKNOWN
