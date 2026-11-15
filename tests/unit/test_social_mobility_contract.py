# mypy: ignore-errors
"""Closed social-mobility contract: vocabulary, tokens, and layer guards."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from analysis.social_mobility_contract import (
    SOCIAL_MOBILITY_ANALYSIS_POLICY_VERSION,
    SOCIAL_MOBILITY_FORBIDDEN_KEYS,
    SocialMobilityAvailability,
    SocialMobilityDomain,
    SocialMobilityError,
    SocialMobilityLayer,
    SocialMobilityMeasure,
    SocialMobilityPersistence,
    assert_social_mobility_layer_separation,
    social_mobility_lineage_token,
    social_mobility_measures_for,
    social_mobility_owner_token,
    social_mobility_pair_token,
    social_mobility_token_hash,
)

pytestmark = pytest.mark.unit


def test_closed_domain_and_measure_vocabulary() -> None:
    assert tuple(domain.value for domain in SocialMobilityDomain) == (
        "resources",
        "skills",
        "social_influence",
        "organization_roles",
        "educational_access",
        "productive_assets",
    )
    assert {
        SocialMobilityAvailability.AVAILABLE.value,
        SocialMobilityAvailability.INSUFFICIENT_SAMPLES.value,
        SocialMobilityAvailability.UNAVAILABLE.value,
    } == {"available", "insufficient_samples", "unavailable"}
    assert {
        SocialMobilityPersistence.PERSISTENT.value,
        SocialMobilityPersistence.MOBILE.value,
        SocialMobilityPersistence.INSUFFICIENT_SAMPLES.value,
        SocialMobilityPersistence.UNAVAILABLE.value,
    } == {"persistent", "mobile", "insufficient_samples", "unavailable"}
    assert SOCIAL_MOBILITY_ANALYSIS_POLICY_VERSION == "social-mobility.v1"


def test_each_domain_has_exactly_one_measure() -> None:
    seen: set[SocialMobilityMeasure] = set()
    for domain in SocialMobilityDomain:
        measures = social_mobility_measures_for(domain)
        assert len(measures) == 1
        assert measures[0] not in seen
        seen.add(measures[0])
    assert len(seen) == 6
    assert {measure.value for measure in seen} == {
        "observed_resource_item_count",
        "known_technique_count",
        "inbound_communication_partner_count",
        "held_organization_role_count",
        "educational_access_receipt_count",
        "observed_productive_asset_count",
    }
    with pytest.raises(SocialMobilityError, match="social_mobility_invalid_input"):
        social_mobility_measures_for("resources")  # type: ignore[arg-type]


def test_tokens_are_prefixed_deterministic_and_distinct() -> None:
    owner = social_mobility_owner_token("entity:alice")
    assert owner == social_mobility_owner_token("entity:alice")
    assert owner.startswith("smo-")
    assert len(owner) == 20
    pair = social_mobility_pair_token(owner, social_mobility_owner_token("entity:bob"))
    lineage = social_mobility_lineage_token(
        owner, social_mobility_owner_token("entity:bob")
    )
    assert pair.startswith("smp-") and len(pair) == 20
    assert lineage.startswith("sml-") and len(lineage) == 20
    assert social_mobility_token_hash("x-", "a", "b") != social_mobility_token_hash(
        "x-", "ab", ""
    )
    with pytest.raises(SocialMobilityError, match="social_mobility_invalid_input"):
        social_mobility_owner_token("")


def test_layer_guard_accepts_homogeneous_groups() -> None:
    assert_social_mobility_layer_separation(
        [_Row(SocialMobilityLayer.OBJECTIVE_OUTCOME)],
        [_Row(SocialMobilityLayer.OWNER_OUTCOME)],
        [_Row(SocialMobilityLayer.ANALYTICAL_MOBILITY)],
    )


def test_layer_guard_rejects_mixed_and_unknown_layers() -> None:
    with pytest.raises(SocialMobilityError, match="social_mobility_layer_leak"):
        assert_social_mobility_layer_separation(
            [
                _Row(SocialMobilityLayer.OBJECTIVE_OUTCOME),
                _Row(SocialMobilityLayer.ANALYTICAL_MOBILITY),
            ]
        )
    with pytest.raises(SocialMobilityError, match="social_mobility_layer_leak"):
        assert_social_mobility_layer_separation([_Row("class")])


def test_layer_guard_rejects_forbidden_dataclass_fields() -> None:
    assert "class" in SOCIAL_MOBILITY_FORBIDDEN_KEYS
    with pytest.raises(SocialMobilityError, match="social_mobility_forbidden_key"):
        assert_social_mobility_layer_separation([_ClassRow()])


@dataclass(frozen=True, slots=True)
class _Row:
    layer: object

    @property
    def source_layers(self) -> tuple[object, ...]:
        return (self.layer,)


@dataclass(frozen=True, slots=True)
class _ClassRow:
    social_class: str = "elite"

    @property
    def source_layers(self) -> tuple[object, ...]:
        return (SocialMobilityLayer.ANALYTICAL_MOBILITY,)
