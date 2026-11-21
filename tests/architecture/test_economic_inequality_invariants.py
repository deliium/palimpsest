# mypy: ignore-errors
"""Versioned pins and registry invariants for V4-24."""

from __future__ import annotations

from analysis.specifications import METRIC_FAMILY_COUNT
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.compatibility import V4_OWNED_CAPABILITY_FLAGS
from simulation.v4_architecture import (
    V4_ANALYSIS_ONLY_CONTEXTS,
    V4_CAPABILITY_FLAGS,
    V4_CONTEXT_BY_ID,
    V4_CONTEXT_MAP_VERSION,
    V4_CONTEXTS,
    V4Authority,
    V4ContextId,
)
from simulation.versioning import (
    TRAVEL_NETWORK_WRITE_PAIR_CODEC,
    V4_EVENT_REUSING_CONTEXTS,
    V4_WRITE_PAIR_RESERVATIONS,
    validate_deepening_write_pairs,
    validate_write_pair_reservations,
)
from world._rules import COMMAND_RULE_MATRIX
from world.events import EVENT_SCHEMA_REPLAY_V27


def test_context_counts_are_fifteen_twelve_eight_four() -> None:
    assert V4_CONTEXT_MAP_VERSION == "v4-context-map-v6"
    assert len(V4_CONTEXTS) == 17
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 9
    assert 12 - len(V4_OWNED_CAPABILITY_FLAGS) == 3


def test_economic_inequality_is_analysis_only_and_flagless() -> None:
    spec = V4_CONTEXT_BY_ID[V4ContextId.ECONOMIC_INEQUALITY]
    assert spec.capability_flag is None
    assert spec.authority is V4Authority.DETACHED_ANALYSIS
    assert spec.owner_packages == ("analysis",)
    assert spec.required_config_seam == "analysis_capture"
    assert spec.uses_existing_events is True
    assert V4ContextId.ECONOMIC_INEQUALITY in V4_ANALYSIS_ONLY_CONTEXTS
    assert V4ContextId.ECONOMIC_INEQUALITY in V4_EVENT_REUSING_CONTEXTS
    assert "economic_inequality" not in V4_CAPABILITY_FLAGS


def test_no_new_write_pair_is_claimed() -> None:
    contexts = {reservation.context_id for reservation in V4_WRITE_PAIR_RESERVATIONS}
    assert V4ContextId.ECONOMIC_INEQUALITY not in contexts
    validate_write_pair_reservations()
    validate_deepening_write_pairs()


def test_catalog_and_closed_surface_counts() -> None:
    assert METRIC_FAMILY_COUNT == 275
    assert len(COMMAND_RULE_MATRIX) == 45
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert EVENT_SCHEMA_REPLAY_V27 == 27
    assert TRAVEL_NETWORK_WRITE_PAIR_CODEC == "v25"
