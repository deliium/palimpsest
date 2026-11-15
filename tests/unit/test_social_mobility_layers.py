# mypy: ignore-errors
"""Objective, owner-scoped, and analytical layers stay separated and token-only."""

from __future__ import annotations

import pytest

from analysis.social_mobility_contract import (
    SocialMobilityAvailability,
    SocialMobilityCoverage,
    SocialMobilityDomain,
    SocialMobilityError,
    SocialMobilityLayer,
    SocialMobilityMeasure,
    SocialMobilityPersistence,
    social_mobility_owner_token,
)
from analysis.social_mobility_rows import (
    SocialMobilityCoverageRow,
    SocialMobilityDomainRow,
    SocialMobilityGenerationRow,
    SocialMobilityLayerBundle,
    SocialMobilityOutcomeRow,
    SocialMobilityPairRow,
)

pytestmark = pytest.mark.unit

OWNER_A = social_mobility_owner_token("entity:a")
OWNER_B = social_mobility_owner_token("entity:b")


def _outcome(domain: SocialMobilityDomain, layer: SocialMobilityLayer):
    return SocialMobilityOutcomeRow(
        owner_token=OWNER_A,
        generation_index=1,
        tick=10,
        window_index=0,
        domain=domain,
        measure=SocialMobilityMeasure(
            {
                SocialMobilityDomain.RESOURCES: "observed_resource_item_count",
                SocialMobilityDomain.SKILLS: "known_technique_count",
                SocialMobilityDomain.SOCIAL_INFLUENCE: (
                    "inbound_communication_partner_count"
                ),
                SocialMobilityDomain.ORGANIZATION_ROLES: (
                    "held_organization_role_count"
                ),
                SocialMobilityDomain.EDUCATIONAL_ACCESS: (
                    "educational_access_receipt_count"
                ),
                SocialMobilityDomain.PRODUCTIVE_ASSETS: (
                    "observed_productive_asset_count"
                ),
            }[domain]
        ),
        quantity=3,
        layer=layer,
    )


def test_bundle_requires_homogeneous_groups() -> None:
    objective = _outcome(
        SocialMobilityDomain.RESOURCES, SocialMobilityLayer.OBJECTIVE_OUTCOME
    )
    owner = _outcome(SocialMobilityDomain.SKILLS, SocialMobilityLayer.OWNER_OUTCOME)
    pair = SocialMobilityPairRow(
        window_index=0,
        ancestor_token=OWNER_A,
        descendant_token=OWNER_B,
        generation_lag=1,
        domain=SocialMobilityDomain.RESOURCES,
        ancestor_quantity=1,
        descendant_quantity=2,
        ancestor_bin=0,
        descendant_bin=1,
        ancestor_window_index=0,
        descendant_window_index=0,
        resolved=True,
    )
    domain_row = SocialMobilityDomainRow(
        window_index=0,
        window_tick=31,
        domain=SocialMobilityDomain.RESOURCES,
        measure=SocialMobilityMeasure.OBSERVED_RESOURCE_ITEM_COUNT,
        pair_count=1,
        resolved_pair_count=1,
        rank_correlation_milli=0,
        same_bin_share_milli=0,
        upward_share_milli=1_000,
        downward_share_milli=0,
        mean_absolute_rank_change_milli=250,
        persistence_direction=SocialMobilityPersistence.MOBILE,
        coverage=SocialMobilityCoverage.COMPLETE,
        availability=SocialMobilityAvailability.INSUFFICIENT_SAMPLES,
    )
    generation_row = SocialMobilityGenerationRow(
        window_index=0,
        window_tick=31,
        generation_index=1,
        owner_count=2,
        pair_count=1,
        comparable=False,
        same_bin_share_milli=0,
        upward_share_milli=1_000,
        downward_share_milli=0,
        coverage=SocialMobilityCoverage.COMPLETE,
        availability=SocialMobilityAvailability.INSUFFICIENT_SAMPLES,
    )
    coverage = SocialMobilityCoverageRow(
        window_index=0,
        window_tick=31,
        generation_count=2,
        owner_count=2,
        genealogy_edge_count=1,
        pair_count=1,
        resolved_pair_count=1,
        unresolved_pair_count=0,
        domain_available_count=0,
        truncated=False,
        coverage=SocialMobilityCoverage.PARTIAL,
    )
    bundle = SocialMobilityLayerBundle(
        objective_rows=(objective,),
        owner_rows=(owner,),
        pair_rows=(pair,),
        domain_rows=(domain_row,),
        generation_rows=(generation_row,),
        coverage_row=coverage,
    )
    assert bundle.objective_rows[0].source_layers == (
        SocialMobilityLayer.OBJECTIVE_OUTCOME,
    )
    assert bundle.owner_rows[0].source_layers == (SocialMobilityLayer.OWNER_OUTCOME,)


def test_domain_layer_must_match_its_evidence_kind() -> None:
    with pytest.raises(SocialMobilityError, match="social_mobility_row_invalid"):
        _outcome(SocialMobilityDomain.SKILLS, SocialMobilityLayer.OBJECTIVE_OUTCOME)


def test_raw_owner_ids_are_rejected() -> None:
    with pytest.raises(SocialMobilityError, match="social_mobility_row_invalid"):
        SocialMobilityOutcomeRow(
            owner_token="agent:alice",
            generation_index=0,
            tick=1,
            window_index=0,
            domain=SocialMobilityDomain.RESOURCES,
            measure=SocialMobilityMeasure.OBSERVED_RESOURCE_ITEM_COUNT,
            quantity=1,
            layer=SocialMobilityLayer.OBJECTIVE_OUTCOME,
        )


def test_mixed_bundle_group_is_rejected() -> None:
    objective = _outcome(
        SocialMobilityDomain.RESOURCES, SocialMobilityLayer.OBJECTIVE_OUTCOME
    )
    owner = _outcome(SocialMobilityDomain.SKILLS, SocialMobilityLayer.OWNER_OUTCOME)
    with pytest.raises(SocialMobilityError, match="social_mobility_layer_leak"):
        SocialMobilityLayerBundle(
            objective_rows=(objective, owner),
            owner_rows=(),
            pair_rows=(),
            domain_rows=(),
            generation_rows=(),
            coverage_row=None,
        )
