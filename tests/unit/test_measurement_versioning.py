# mypy: ignore-errors

"""V4-29 physical deepening registration without weakening authority."""

from __future__ import annotations

from dataclasses import replace

import pytest

from simulation.v4_architecture import (
    V4_CONTEXT_BY_ID,
    V4_CONTEXT_MAP_VERSION,
    V4_CONTEXTS,
    V4Authority,
    V4ContextId,
    validate_v4_contexts,
)
from simulation.versioning import (
    MEASUREMENT_WRITE_PAIR_CODEC,
    MEASUREMENT_WRITE_PAIR_EVENT,
    TRAVEL_NETWORK_WRITE_PAIR_CODEC,
    TRAVEL_NETWORK_WRITE_PAIR_EVENT,
    V4_DEEPENING_WRITE_PAIRS,
    V4_EVENT_REUSING_CONTEXTS,
    V4_WRITE_PAIR_RESERVATIONS,
    DeepeningWritePair,
    validate_deepening_write_pairs,
    validate_write_pair_reservations,
)

pytestmark = pytest.mark.unit


def test_measurement_pair_is_contiguous_after_travel() -> None:
    assert (TRAVEL_NETWORK_WRITE_PAIR_EVENT, TRAVEL_NETWORK_WRITE_PAIR_CODEC) == (
        27,
        "v25",
    )
    assert (MEASUREMENT_WRITE_PAIR_EVENT, MEASUREMENT_WRITE_PAIR_CODEC) == (
        28,
        "v26",
    )
    assert [pair.event_schema for pair in V4_DEEPENING_WRITE_PAIRS] == [27, 28]
    assert [pair.codec_version for pair in V4_DEEPENING_WRITE_PAIRS] == ["v25", "v26"]
    validate_deepening_write_pairs()


def test_reserved_slots_are_untouched() -> None:
    assert [item.event_schema for item in V4_WRITE_PAIR_RESERVATIONS] == [
        23,
        24,
        25,
        26,
    ]
    assert [item.codec_version for item in V4_WRITE_PAIR_RESERVATIONS] == [
        "v21",
        "v22",
        "v23",
        "v24",
    ]


def test_science_is_no_longer_exclusively_event_reusing() -> None:
    assert V4ContextId.SCIENCE not in V4_EVENT_REUSING_CONTEXTS
    spec = V4_CONTEXT_BY_ID[V4ContextId.SCIENCE]
    assert spec.authority is V4Authority.OWNER_SCOPED
    assert spec.uses_existing_events is False
    assert "world" not in spec.owner_packages


def test_context_map_revision_advances_without_counts() -> None:
    assert V4_CONTEXT_MAP_VERSION == "v4-context-map-v6"
    assert len(V4_CONTEXTS) == 17


def test_missing_science_coverage_is_rejected() -> None:
    with pytest.raises(ValueError, match="v4_pair_uncovered_context"):
        validate_write_pair_reservations(deepening_pairs=())


def test_reuse_and_deepening_conflict_is_rejected() -> None:
    with pytest.raises(ValueError, match="v4_pair_reuse_deepening_conflict"):
        validate_write_pair_reservations(
            reusing_contexts=V4_EVENT_REUSING_CONTEXTS | {V4ContextId.SCIENCE}
        )


def test_unowned_deepening_context_is_rejected() -> None:
    pair = DeepeningWritePair(
        context_id=V4ContextId.DISASTERS,
        event_schema=28,
        codec_version="v26",
        reason="not owned",
    )
    with pytest.raises(ValueError, match="v4_deepening_pair_unowned_context"):
        validate_deepening_write_pairs((pair,))


def test_science_remains_owner_scoped_without_world_ownership() -> None:
    contexts = tuple(
        replace(spec, owner_packages=(*spec.owner_packages, "world"))
        if spec.context_id is V4ContextId.SCIENCE
        else spec
        for spec in V4_CONTEXTS
    )
    with pytest.raises(ValueError, match="v4_context_world_authority"):
        validate_v4_contexts(contexts)
