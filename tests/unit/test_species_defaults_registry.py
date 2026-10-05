"""Unit tests for closed species-defaults registry."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from simulation.new_agent_initialization import (
    SPECIES_DEFAULT_V1,
    species_defaults_for,
)

_LOG = logging.getLogger("tests.species_defaults_registry")


def test_species_default_v1_fresh_per_owner() -> None:
    _LOG.debug("case_id=species_default_v1_fresh_per_owner")
    a = species_defaults_for(SPECIES_DEFAULT_V1, agent_id=AgentId("agent-a"))
    b = species_defaults_for(SPECIES_DEFAULT_V1, agent_id=AgentId("agent-b"))
    assert a.species_defaults_id == SPECIES_DEFAULT_V1
    assert a.cognition.agent_id == AgentId("agent-a")
    assert b.cognition.agent_id == AgentId("agent-b")
    assert a.drive_profile.owner_id == AgentId("agent-a")
    assert b.drive_profile.owner_id == AgentId("agent-b")
    assert a.cognition is not b.cognition
    assert a.drive_profile is not b.drive_profile
    # Default pack enables reconstructive memory mode but no content ledgers.
    assert a.cognition.drive_overrides == ()
    assert b.cognition.drive_overrides == ()
    assert a.cognition.cultural_narrative_mode.value == "disabled"
    assert a.cognition.skill_learning_mode.value == "disabled"


def test_unknown_species_defaults_id_fails_closed() -> None:
    _LOG.debug("case_id=unknown_species_defaults_id_fails_closed")
    with pytest.raises(ValueError, match="unknown_species_defaults_id"):
        species_defaults_for("species_default_missing", agent_id=AgentId("agent-1"))
