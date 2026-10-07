"""Checkpoint selector priority for knowledge repositories (Task 20)."""

from __future__ import annotations

import logging

import pytest

from simulation.engine import select_checkpoint_schema
from simulation.persistence import checkpoint_schema_for_production
from world.events import (
    EVENT_SCHEMA_REPLAY_V12,
    EVENT_SCHEMA_REPLAY_V13,
    EVENT_SCHEMA_REPLAY_V14,
)

pytestmark = pytest.mark.unit
_LOG = logging.getLogger("tests.checkpoint_schema_knowledge_repositories")


def test_repository_plus_durable_selects_v14_v11(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG):
        schema, codec = checkpoint_schema_for_production(
            production_active=False,
            knowledge_repositories_active=True,
            durable_records_active=True,
        )
        agreed = select_checkpoint_schema(
            production_active=False,
            dynamics_active=False,
            knowledge_repositories_active=True,
            durable_records_active=True,
        )
    assert (schema, codec) == (EVENT_SCHEMA_REPLAY_V14, "v11")
    assert agreed == (EVENT_SCHEMA_REPLAY_V14, "v11")
    _LOG.debug("selected_pair schema=%s codec=%s", schema, codec)


def test_repository_beats_dependency_care() -> None:
    schema, codec = checkpoint_schema_for_production(
        production_active=False,
        knowledge_repositories_active=True,
        durable_records_active=True,
        dependency_care_active=True,
    )
    assert (schema, codec) == (EVENT_SCHEMA_REPLAY_V14, "v11")
    # Dependency-care alone remains V12 when repository off.
    dep_only = checkpoint_schema_for_production(
        production_active=False,
        knowledge_repositories_active=False,
        durable_records_active=False,
        dependency_care_active=True,
    )
    assert dep_only == (EVENT_SCHEMA_REPLAY_V12, "v9")


def test_durable_without_repository_stays_v13() -> None:
    schema, codec = checkpoint_schema_for_production(
        production_active=False,
        knowledge_repositories_active=False,
        durable_records_active=True,
    )
    assert (schema, codec) == (EVENT_SCHEMA_REPLAY_V13, "v10")
