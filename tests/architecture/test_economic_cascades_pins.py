# mypy: ignore-errors
"""Aggregate version pins that V4-26 must not change."""

from __future__ import annotations

from pathlib import Path

from analysis.specifications import METRIC_FAMILY_COUNT
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.compatibility import V4_OWNED_CAPABILITY_FLAGS
from simulation.v4_architecture import (
    V4_CAPABILITY_FLAGS,
    V4_CONTEXT_MAP_VERSION,
    V4_CONTEXTS,
)
from simulation.versioning import (
    TRAVEL_NETWORK_WRITE_PAIR_CODEC,
    V4_WRITE_PAIR_RESERVATIONS,
)
from world._rules import COMMAND_RULE_MATRIX
from world.events import EVENT_SCHEMA_REPLAY_V27

ROOT = Path(__file__).resolve().parents[2]


def test_context_pins() -> None:
    assert V4_CONTEXT_MAP_VERSION == "v4-context-map-v6"
    assert len(V4_CONTEXTS) == 17
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 9
    assert 12 - len(V4_OWNED_CAPABILITY_FLAGS) == 3


def test_metric_catalog_pin() -> None:
    assert METRIC_FAMILY_COUNT == 271


def test_closed_surface_pins() -> None:
    assert len(COMMAND_RULE_MATRIX) == 45
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert EVENT_SCHEMA_REPLAY_V27 == 27
    assert TRAVEL_NETWORK_WRITE_PAIR_CODEC == "v25"


def test_no_new_runner_schema_or_migration() -> None:
    for path in (ROOT / "src").rglob("*.py"):
        assert "runner-config-v58" not in path.read_text(encoding="utf-8"), path
    assert not list((ROOT / "alembic" / "versions").glob("0018*"))


def test_write_pair_reservations_stay_unchanged() -> None:
    assert len(V4_WRITE_PAIR_RESERVATIONS) == 4
