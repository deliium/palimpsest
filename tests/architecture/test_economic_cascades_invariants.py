# mypy: ignore-errors
"""Registry and ownership invariants for V4-26 economic cascades."""

from __future__ import annotations

from pathlib import Path

from simulation.compatibility import V4_OWNED_CAPABILITY_FLAGS
from simulation.v4_architecture import (
    V4_ANALYSIS_ONLY_CONTEXTS,
    V4_CAPABILITY_FLAGS,
    V4_CONTEXT_BY_ID,
    V4_CONTEXT_MAP_VERSION,
    V4_CONTEXTS,
    V4Authority,
    V4ContextId,
    validate_v4_contexts,
)
from simulation.versioning import (
    V4_EVENT_REUSING_CONTEXTS,
    V4_WRITE_PAIR_RESERVATIONS,
    validate_deepening_write_pairs,
    validate_write_pair_reservations,
)

ROOT = Path(__file__).resolve().parents[2]


def test_context_counts_are_seventeen_twelve_eight_four() -> None:
    validate_v4_contexts()
    assert V4_CONTEXT_MAP_VERSION == "v4-context-map-v6"
    assert len(V4_CONTEXTS) == 17
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 10
    assert 12 - len(V4_OWNED_CAPABILITY_FLAGS) == 2


def test_economic_cascades_is_analysis_only_and_flagless() -> None:
    spec = V4_CONTEXT_BY_ID[V4ContextId.ECONOMIC_CASCADES]
    assert spec.capability_flag is None
    assert spec.authority is V4Authority.DETACHED_ANALYSIS
    assert spec.owner_packages == ("analysis",)
    assert spec.required_config_seam == "analysis_capture"
    assert spec.uses_existing_events is True
    assert spec.prerequisite_contexts == (V4ContextId.SUPPLY_CHAINS,)
    assert V4ContextId.ECONOMIC_CASCADES in V4_ANALYSIS_ONLY_CONTEXTS
    assert V4ContextId.ECONOMIC_CASCADES in V4_EVENT_REUSING_CONTEXTS
    assert "economic_cascades" not in V4_CAPABILITY_FLAGS
    assert tuple(item.context_id for item in V4_CONTEXTS)[-1] is (
        V4ContextId.ECONOMIC_CASCADES
    )


def test_no_new_write_pair_is_claimed() -> None:
    contexts = {reservation.context_id for reservation in V4_WRITE_PAIR_RESERVATIONS}
    assert V4ContextId.ECONOMIC_CASCADES not in contexts
    validate_write_pair_reservations()
    validate_deepening_write_pairs()


def test_no_runner_schema_or_migration_is_added() -> None:
    for path in (ROOT / "src").rglob("*.py"):
        assert "runner-config-v58" not in path.read_text(encoding="utf-8"), path
    assert sorted((ROOT / "alembic" / "versions").glob("0018_*.py")) == []
