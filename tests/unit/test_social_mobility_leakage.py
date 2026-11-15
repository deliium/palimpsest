# mypy: ignore-errors
"""Layer and token leakage guards for rows, snapshots, and metric documents."""

from __future__ import annotations

import pytest

from analysis.social_mobility_analysis import harvest_social_mobility_analysis
from analysis.social_mobility_contract import (
    SOCIAL_MOBILITY_FORBIDDEN_KEYS,
    SocialMobilityCoverage,
    SocialMobilityDomain,
    SocialMobilityLayer,
    SocialMobilityMeasure,
    social_mobility_lineage_token,
    social_mobility_owner_token,
)
from analysis.social_mobility_genealogy import SocialMobilityGenealogyHarvest
from analysis.social_mobility_metrics import (
    compute_resource_mobility,
    compute_social_mobility_coverage,
)
from analysis.social_mobility_outcomes import SocialMobilityOutcomeHarvest
from analysis.social_mobility_rows import (
    SocialMobilityGenealogyRow,
    SocialMobilityLineageEntry,
    SocialMobilityOutcomeRow,
)
from experiments.social_mobility_publication import (
    compose_social_mobility_snapshot,
)

pytestmark = pytest.mark.unit


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


def _field_names(row: object) -> set[str]:
    return set(getattr(type(row), "__dataclass_fields__", {}))


def test_objective_rows_carry_no_owner_claim_fields() -> None:
    analysis = _analysis()
    for row in analysis.objective_rows:
        assert row.layer is SocialMobilityLayer.OBJECTIVE_OUTCOME
        assert not _field_names(row) & {
            "organization_token",
            "claim",
            "stance",
            "belief",
            "custody",
        }


def test_analytical_rows_carry_no_raw_owner_ids() -> None:
    analysis = _analysis()
    assert analysis.domain_rows
    for row in (
        *analysis.domain_rows,
        *analysis.generation_rows,
        *analysis.lag_rows,
        *analysis.pair_rows,
    ):
        rendered = repr(row)
        assert "entity:" not in rendered
        assert "agent:" not in rendered


def test_snapshot_rows_expose_no_owner_or_pair_tokens() -> None:
    snapshot = compose_social_mobility_snapshot(_analysis(), run_id="run-1")
    for row in (*snapshot.domains, *snapshot.generations, *snapshot.lags):
        names = _field_names(row)
        assert not names & {
            "owner_token",
            "ancestor_token",
            "descendant_token",
            "pair_token",
            "lineage_token",
        }
        assert not names & SOCIAL_MOBILITY_FORBIDDEN_KEYS


def test_metric_documents_reject_forbidden_value_keys() -> None:
    analysis = _analysis()
    document = compute_resource_mobility(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    for key in document.values:
        assert key.lower() not in SOCIAL_MOBILITY_FORBIDDEN_KEYS
    coverage = compute_social_mobility_coverage(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    for key in coverage.values:
        assert key.lower() not in SOCIAL_MOBILITY_FORBIDDEN_KEYS
    assert "owner_token" not in document.values
