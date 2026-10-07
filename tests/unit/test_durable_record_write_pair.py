"""Durable records select replay-v13 / codec v10 ahead of dependency-care."""

from __future__ import annotations

import pytest

from simulation.engine import select_checkpoint_schema
from simulation.persistence import checkpoint_schema_for_production
from world.events import EVENT_SCHEMA_REPLAY_V12, EVENT_SCHEMA_REPLAY_V13

pytestmark = pytest.mark.unit


def test_durable_beats_dependency_care_write_pair() -> None:
    schema, codec = checkpoint_schema_for_production(
        production_active=False,
        durable_records_active=True,
        dependency_care_active=True,
        kinship_active=True,
        artifacts_active=True,
    )
    assert schema == EVENT_SCHEMA_REPLAY_V13
    assert codec == "v10"
    agreed = select_checkpoint_schema(
        production_active=False,
        dynamics_active=False,
        durable_records_active=True,
        dependency_care_active=True,
        kinship_active=True,
        artifacts_active=True,
    )
    assert agreed == (EVENT_SCHEMA_REPLAY_V13, "v10")


def test_dependency_care_unchanged_without_durable() -> None:
    schema, codec = checkpoint_schema_for_production(
        production_active=False,
        durable_records_active=False,
        dependency_care_active=True,
    )
    assert schema == EVENT_SCHEMA_REPLAY_V12
    assert codec == "v9"
