# mypy: ignore-errors
"""Locked border cognition policy."""

from __future__ import annotations

import dataclasses

import pytest

from agents.cognition.borders import (
    BORDERS_POLICY_VERSION,
    BordersPolicy,
    default_borders_policy,
)


def test_policy_versions_and_numbers_are_locked() -> None:
    policy = default_borders_policy()
    assert policy.version == BORDERS_POLICY_VERSION
    assert policy.min_claim_strength == 0.40
    assert policy.max_domains == 8
    assert policy.max_locations_per_domain == 8
    assert policy.max_boundary_edges_per_domain == 32
    assert policy.max_agreements == 8
    assert policy.max_access_expectations == 16
    assert policy.max_disputes == 8
    assert policy.max_evidence_per_row == 32
    assert policy.max_ledger_rows == 128
    assert policy.max_domain_evidence_age_ticks == 256
    assert policy.max_agreement_age_ticks == 128
    assert policy.min_recognition_parties == 2
    assert policy.agreement_acceptance_min_parties == 2
    assert policy.overlap_min_locations == 1
    assert policy.domain_contiguity_required is True
    assert policy.boundary_edges_observed_only is True
    assert policy.access_expectations_bind_commands is False
    assert policy.agreements_bind_commands is False


def test_any_changed_policy_value_is_rejected() -> None:
    for item in dataclasses.fields(BordersPolicy):
        if item.name == "version":
            continue
        current = getattr(BordersPolicy(), item.name)
        if isinstance(current, bool):
            changed = not current
        elif isinstance(current, float):
            changed = current + 0.01
        else:
            changed = current + 1
        with pytest.raises(ValueError):
            BordersPolicy(**{item.name: changed})
    with pytest.raises(ValueError):
        BordersPolicy(version="borders-claims.v2")


def test_policy_helpers_return_the_only_accepted_values() -> None:
    assert default_borders_policy() == default_borders_policy()


def test_no_command_binding_switch_is_honored() -> None:
    with pytest.raises(ValueError):
        BordersPolicy(access_expectations_bind_commands=True)
    with pytest.raises(ValueError):
        BordersPolicy(agreements_bind_commands=True)
