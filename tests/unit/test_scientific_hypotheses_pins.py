# mypy: ignore-errors
"""Current-state pins for V4-27 scientific hypotheses."""

from __future__ import annotations

from pathlib import Path

from analysis.specifications import METRIC_FAMILY_COUNT, MetricFamilyId
from observer import SEMANTIC_EVENT_TYPES
from simulation.compatibility import ALEMBIC_HEAD_REVISION, OBSERVER_PROTOCOL_VERSION
from simulation.v4_architecture import (
    V4_CAPABILITY_FLAGS,
    V4_CONTEXT_MAP_VERSION,
    V4_CONTEXTS,
    V4ContextId,
    validate_v4_contexts,
)
from simulation.versioning import (
    TRAVEL_NETWORK_WRITE_PAIR_CODEC,
    V4_DEEPENING_WRITE_PAIRS,
    V4_WRITE_PAIR_RESERVATIONS,
)
from world._rules import COMMAND_RULE_MATRIX
from world.events import EVENT_SCHEMA_REPLAY_V27

ROOT = Path(__file__).resolve().parents[2]


def test_science_ownership_pins() -> None:
    from simulation.compatibility import V4_OWNED_CAPABILITY_FLAGS

    validate_v4_contexts()
    assert V4_CONTEXT_MAP_VERSION == "v4-context-map-v6"
    assert len(V4_CONTEXTS) == 17
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert V4_OWNED_CAPABILITY_FLAGS == frozenset(
        {
            "organizations",
            "formal_rules",
            "legal_disputes",
            "diplomacy",
            "organized_conflict",
            "infrastructure_networks",
            "supply_chains",
            "markets_credit",
            "science",
            "epidemics",
        }
    )
    assert set(V4_CAPABILITY_FLAGS) - V4_OWNED_CAPABILITY_FLAGS == {
                "ecological_feedback",
        "disasters",
    }


def test_catalog_and_wire_pins() -> None:
    assert METRIC_FAMILY_COUNT == 275
    assert tuple(item.value for item in MetricFamilyId)[244:250] == (
        "scientific_hypothesis_structure",
        "scientific_hypothesis_evidence",
        "scientific_hypothesis_test_activity",
        "scientific_hypothesis_revisions",
        "scientific_hypothesis_provenance",
        "scientific_hypothesis_prediction_outcomes",
    )
    assert tuple(item.value for item in MetricFamilyId)[250:256] == (
        "scientific_replication_design_lineage",
        "scientific_replication_conditions",
        "scientific_replication_results",
        "scientific_replication_uncertainty",
        "scientific_replication_relationships",
        "scientific_replication_social_interpretation",
    )
    assert len(COMMAND_RULE_MATRIX) == 45
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert EVENT_SCHEMA_REPLAY_V27 == 27
    assert TRAVEL_NETWORK_WRITE_PAIR_CODEC == "v25"
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"


def test_science_adds_no_write_pair_or_migration() -> None:
    reserved = {item.context_id for item in V4_WRITE_PAIR_RESERVATIONS}
    deepening = {item.context_id for item in V4_DEEPENING_WRITE_PAIRS}
    assert V4ContextId.SCIENCE not in reserved
    assert V4ContextId.SCIENCE in deepening
    assert sorted((ROOT / "alembic" / "versions").glob("0018_*.py")) == []


def test_no_v57_or_v2_route_exists() -> None:
    from simulation.runner_models import SUPPORTED_RUNNER_SCHEMA_VERSIONS

    assert "runner-config-v60" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    for path in (ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "runner-config-v60" not in text, path
        assert '"/v2' not in text, path


def test_science_off_flags_are_identical() -> None:
    from simulation.runner_models import V4CapabilityFlags

    assert V4CapabilityFlags(science=False) == V4CapabilityFlags()
