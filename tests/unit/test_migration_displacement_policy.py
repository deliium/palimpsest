# mypy: ignore-errors
"""Locked migration-displacement cognition and analysis policies."""

from __future__ import annotations

import dataclasses

import pytest

from agents.cognition.migration_displacement import (
    MIGRATION_DISPLACEMENT_POLICY_VERSION,
    MigrationDisplacementPolicy,
    default_migration_displacement_policy,
)
from agents.cognition.regional_migration import (
    REGIONAL_DESTINATION_MEMORY_POLICY_VERSION,
    REGIONAL_MIGRATION_COGNITION_POLICY_VERSION,
)
from analysis.migration_displacement_policy import (
    MIGRATION_DISPLACEMENT_ANALYSIS_POLICY_VERSION,
    MigrationDisplacementAnalysisPolicy,
    MigrationDisplacementAnalysisPolicyError,
    default_migration_displacement_analysis_policy,
)

pytestmark = pytest.mark.unit


def test_policy_versions_and_numbers_are_locked() -> None:
    policy = default_migration_displacement_policy()
    assert policy.version == MIGRATION_DISPLACEMENT_POLICY_VERSION
    assert policy.version == "migration-displacement.v1"
    assert policy.max_intents == 8
    assert policy.max_route_beliefs == 16
    assert policy.max_cause_evidence == 32
    assert policy.max_cluster_beliefs == 8
    assert policy.max_integration_beliefs == 8
    assert policy.max_wave_observations == 8
    assert policy.max_route_locations == 4
    assert policy.max_cluster_members == 16
    assert policy.max_evidence_per_row == 16
    assert policy.max_ledger_rows == 96
    assert policy.max_intent_age_ticks == 128
    assert policy.max_route_age_ticks == 256
    assert policy.max_cause_age_ticks == 256
    assert policy.max_cluster_age_ticks == 256
    assert policy.max_integration_age_ticks == 256
    assert policy.max_wave_age_ticks == 128
    assert policy.min_intent_confidence == 0.35
    assert policy.min_cause_support == 1
    assert policy.max_destination_bias == 0.25
    assert policy.route_beliefs_observed_only is True
    assert policy.causes_are_beliefs is True
    assert policy.intents_bind_commands is False
    assert policy.clusters_bind_commands is False
    assert policy.integration_beliefs_are_truth is False

    analysis = default_migration_displacement_analysis_policy()
    assert analysis.version == MIGRATION_DISPLACEMENT_ANALYSIS_POLICY_VERSION
    assert analysis.version == "migration-displacement-analysis.v1"
    assert analysis.wave_window_ticks == 12
    assert analysis.max_wave_gap_ticks == 6
    assert analysis.min_wave_participants == 2
    assert analysis.min_wave_distinct_origins == 1
    assert analysis.min_wave_route_overlap == 1
    assert analysis.cause_window_ticks == 16
    assert analysis.min_cause_evidence == 1
    assert analysis.displacement_min_independent_causes == 1
    assert analysis.mixed_min_displacement_causes == 1
    assert analysis.mixed_min_opportunity_causes == 1
    assert analysis.integration_window_ticks == 32
    assert analysis.min_residence_ticks == 4
    assert analysis.cluster_window_ticks == 32
    assert analysis.min_cluster_members == 2
    assert analysis.max_candidates_per_run == 512
    assert analysis.max_pairs_per_run == 4096
    assert analysis.max_rows_per_family == 5000
    assert analysis.quantum == 0.000001


def test_any_changed_policy_value_is_rejected() -> None:
    for item in dataclasses.fields(MigrationDisplacementPolicy):
        if item.name == "version":
            continue
        current = getattr(MigrationDisplacementPolicy(), item.name)
        if isinstance(current, bool):
            changed = not current
        elif isinstance(current, float):
            changed = current + 0.01
        else:
            changed = current + 1
        with pytest.raises(ValueError, match=f"{item.name}: unsupported_policy"):
            MigrationDisplacementPolicy(**{item.name: changed})
    with pytest.raises(ValueError, match="unsupported_policy"):
        MigrationDisplacementPolicy(version="migration-displacement.v2")
    # a bool or float masquerading as an int is also rejected
    with pytest.raises(ValueError):
        MigrationDisplacementPolicy(max_intents=8.0)
    with pytest.raises(ValueError):
        MigrationDisplacementPolicy(min_cause_support=True)

    for item in dataclasses.fields(MigrationDisplacementAnalysisPolicy):
        if item.name == "version":
            continue
        current = getattr(MigrationDisplacementAnalysisPolicy(), item.name)
        changed = current + 0.01 if isinstance(current, float) else current + 1
        with pytest.raises(MigrationDisplacementAnalysisPolicyError) as raised:
            MigrationDisplacementAnalysisPolicy(**{item.name: changed})
        assert raised.value.code == "unsupported_policy"
    with pytest.raises(MigrationDisplacementAnalysisPolicyError):
        MigrationDisplacementAnalysisPolicy(
            version="migration-displacement-analysis.v2"
        )
    with pytest.raises(MigrationDisplacementAnalysisPolicyError):
        MigrationDisplacementAnalysisPolicy(max_pairs_per_run=4096.0)


def test_policy_helpers_return_the_only_accepted_values() -> None:
    assert default_migration_displacement_policy() == MigrationDisplacementPolicy()
    assert default_migration_displacement_policy() == (
        default_migration_displacement_policy()
    )
    assert default_migration_displacement_analysis_policy() == (
        MigrationDisplacementAnalysisPolicy()
    )


def test_no_command_binding_or_refugee_switch_is_honored() -> None:
    with pytest.raises(ValueError, match="intents_bind_commands"):
        MigrationDisplacementPolicy(intents_bind_commands=True)
    with pytest.raises(ValueError, match="clusters_bind_commands"):
        MigrationDisplacementPolicy(clusters_bind_commands=True)
    with pytest.raises(ValueError, match="integration_beliefs_are_truth"):
        MigrationDisplacementPolicy(integration_beliefs_are_truth=True)
    with pytest.raises(ValueError, match="causes_are_beliefs"):
        MigrationDisplacementPolicy(causes_are_beliefs=False)
    with pytest.raises(ValueError, match="route_beliefs_observed_only"):
        MigrationDisplacementPolicy(route_beliefs_observed_only=False)
    banned = {"enforce", "permission", "refugee", "wellbeing", "assimilation", "score"}
    names = {item.name for item in dataclasses.fields(MigrationDisplacementPolicy)}
    names |= {
        item.name for item in dataclasses.fields(MigrationDisplacementAnalysisPolicy)
    }
    for name in names:
        assert not any(word in name for word in banned), name
    with pytest.raises(TypeError):
        MigrationDisplacementPolicy(refugee_status=True)
    with pytest.raises(TypeError):
        MigrationDisplacementPolicy(enforce=True)


def test_existing_regional_policies_are_unchanged() -> None:
    assert REGIONAL_DESTINATION_MEMORY_POLICY_VERSION == (
        "regional-destination-memory.v1"
    )
    assert REGIONAL_MIGRATION_COGNITION_POLICY_VERSION == (
        "regional-migration-cognition.v1"
    )
