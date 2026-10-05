"""Checkpoint schema priority for new-agent provenance (v10/v7)."""

from __future__ import annotations

import logging

from simulation.engine import select_checkpoint_schema
from simulation.persistence import checkpoint_schema_for_production
from world.events import EVENT_SCHEMA_REPLAY_V9, EVENT_SCHEMA_REPLAY_V10

_LOG = logging.getLogger("tests.checkpoint_schema_new_agent_provenance")


def test_provenance_active_outranks_lifecycle() -> None:
    _LOG.debug("case_id=provenance_over_lifecycle")
    assert checkpoint_schema_for_production(
        production_active=True,
        dynamics_active=True,
        artifacts_active=True,
        lifecycle_active=True,
        new_agent_provenance_active=True,
    ) == (EVENT_SCHEMA_REPLAY_V10, "v7")
    assert checkpoint_schema_for_production(
        production_active=True,
        dynamics_active=True,
        artifacts_active=True,
        lifecycle_active=True,
        new_agent_provenance_active=False,
    ) == (EVENT_SCHEMA_REPLAY_V9, "v6")


def test_select_checkpoint_schema_agrees_on_provenance_pair() -> None:
    _LOG.debug("case_id=select_provenance_pair")
    assert select_checkpoint_schema(
        production_active=True,
        dynamics_active=False,
        artifacts_active=False,
        lifecycle_active=True,
        new_agent_provenance_active=True,
    ) == (EVENT_SCHEMA_REPLAY_V10, "v7")
