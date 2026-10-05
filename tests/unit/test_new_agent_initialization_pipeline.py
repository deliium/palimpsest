"""Shared NewAgentInitialization pre-admit body builder."""

from __future__ import annotations

import logging

import pytest

from simulation.new_agent_initialization import (
    OriginRef,
    build_entrant_body_from_init,
    creation_config_fingerprint,
    default_new_agent_initialization_spec,
    enforce_spawn_location_for_candidate,
)
from world.identifiers import EntityId
from world.lifecycle import DependencyStatus, LifecycleStageId

_LOG = logging.getLogger("tests.new_agent_initialization_pipeline")


def test_build_entrant_body_records_initial_conditions() -> None:
    _LOG.debug("case_id=build_entrant_body")
    spec = default_new_agent_initialization_spec()
    fingerprint = creation_config_fingerprint(
        spec, demographic_policy_id="fixed_interval_entry"
    )
    prepared = build_entrant_body_from_init(
        init_spec=spec,
        body_id=EntityId("body-new"),
        location_id=EntityId("loc-1"),
        stage=LifecycleStageId("infant"),
        dependency_status=DependencyStatus.DEPENDENT,
        creation_reason="demographic_policy",
        origin_refs=(),
        creation_config_id=fingerprint,
    )
    assert prepared.location_id.value == "loc-1"
    assert prepared.creation_config_id == fingerprint
    conditions = prepared.initial_conditions.canonical_payload()
    assert conditions["location_id"] == "loc-1"
    assert conditions["stage"] == "infant"
    assert "health" in conditions


def test_spawn_location_defer_to_candidate() -> None:
    _LOG.debug("case_id=spawn_defer")
    spec = default_new_agent_initialization_spec()
    resolved = enforce_spawn_location_for_candidate(
        init_spec=spec,
        candidate_location_id=EntityId("loc-1"),
        provenance_is_demographic=True,
    )
    assert resolved.value == "loc-1"


def test_origin_ref_kinship_forbidden_at_construction() -> None:
    _LOG.debug("case_id=origin_ref_kinship")
    with pytest.raises(ValueError, match="origin_ref_kinship_forbidden"):
        OriginRef(role="parent", agent_id="agent-1")
