"""Knowledge repositories select replay-v14 / codec v11 ahead of durable."""

from __future__ import annotations

import pytest

from simulation.engine import select_checkpoint_schema
from simulation.persistence import checkpoint_schema_for_production
from world.events import EVENT_SCHEMA_REPLAY_V13, EVENT_SCHEMA_REPLAY_V14

pytestmark = pytest.mark.unit


def test_repositories_beat_durable_write_pair() -> None:
    schema, codec = checkpoint_schema_for_production(
        production_active=False,
        knowledge_repositories_active=True,
        durable_records_active=True,
        dependency_care_active=True,
        kinship_active=True,
        artifacts_active=True,
    )
    assert schema == EVENT_SCHEMA_REPLAY_V14
    assert codec == "v11"
    agreed = select_checkpoint_schema(
        production_active=False,
        dynamics_active=False,
        knowledge_repositories_active=True,
        durable_records_active=True,
        dependency_care_active=True,
        kinship_active=True,
        artifacts_active=True,
    )
    assert agreed == (EVENT_SCHEMA_REPLAY_V14, "v11")


def test_durable_unchanged_without_repositories() -> None:
    schema, codec = checkpoint_schema_for_production(
        production_active=False,
        knowledge_repositories_active=False,
        durable_records_active=True,
    )
    assert schema == EVENT_SCHEMA_REPLAY_V13
    assert codec == "v10"
