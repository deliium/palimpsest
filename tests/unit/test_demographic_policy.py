"""Demographic policy unit tests."""

from __future__ import annotations

import logging

import pytest

from simulation.demographic_policy import (
    DemographicPopulationSnapshot,
    demographic_policy_for,
)

_LOG = logging.getLogger("tests.demographic_policy")


def test_disabled_policy_proposes_nothing() -> None:
    _LOG.debug("case_id=disabled_noop")
    policy = demographic_policy_for("disabled")
    snap = DemographicPopulationSnapshot(
        tick=5,
        living_population=1,
        max_population=8,
        known_agent_ids=frozenset(),
        known_body_ids=frozenset(),
    )
    assert policy.propose_entries(snapshot=snap, params={}, rng_draw=0) == ()


def test_fixed_interval_proposes_on_interval() -> None:
    _LOG.debug("case_id=fixed_interval_hit")
    policy = demographic_policy_for("fixed_interval_entry")
    params = {
        "interval_ticks": 5,
        "entries_per_interval": 2,
        "name_prefix": "entrant",
        "cohort_id_prefix": "cohort",
        "generation_index": 1,
        "spawn_location_id": "loc-1",
    }
    snap = DemographicPopulationSnapshot(
        tick=5,
        living_population=1,
        max_population=8,
        known_agent_ids=frozenset(),
        known_body_ids=frozenset(),
    )
    candidates = policy.propose_entries(snapshot=snap, params=params, rng_draw=0)
    assert len(candidates) == 2
    assert candidates[0].sort_key <= candidates[1].sort_key
    assert candidates[0].agent_id.value.startswith("entrant-")


def test_fixed_interval_respects_population_cap() -> None:
    _LOG.debug("case_id=fixed_interval_cap")
    policy = demographic_policy_for("fixed_interval_entry")
    params = {
        "interval_ticks": 5,
        "entries_per_interval": 5,
        "name_prefix": "entrant",
        "cohort_id_prefix": "cohort",
        "generation_index": 1,
        "spawn_location_id": "loc-1",
    }
    snap = DemographicPopulationSnapshot(
        tick=5,
        living_population=7,
        max_population=8,
        known_agent_ids=frozenset(),
        known_body_ids=frozenset(),
    )
    candidates = policy.propose_entries(snapshot=snap, params=params, rng_draw=0)
    assert len(candidates) == 1


def test_unknown_policy_fails_closed() -> None:
    _LOG.debug("case_id=unknown_policy")
    with pytest.raises(ValueError, match="unknown_demographic_policy_id"):
        demographic_policy_for("mating")
