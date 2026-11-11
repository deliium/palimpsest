"""Reserved V4 write pairs: contiguous, covered, and never applied in V4-01."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, cast

import pytest

import world.events
from simulation.persistence import (
    ACCEPTED_EVENT_SCHEMA_VERSIONS,
    ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
)
from simulation.v4_architecture import V4_CONTEXTS, V4ContextId
from simulation.versioning import (
    TRAVEL_NETWORK_WRITE_PAIR_CODEC,
    TRAVEL_NETWORK_WRITE_PAIR_EVENT,
    V4_DEEPENING_WRITE_PAIRS,
    V4_EVENT_REUSING_CONTEXTS,
    V4_WRITE_PAIR_RESERVATIONS,
    WritePairReservation,
    reservation_for_context,
    validate_deepening_write_pairs,
    validate_write_pair_reservations,
)
from world.events import (
    EVENT_SCHEMA_REPLAY_V22,
    EVENT_SCHEMA_REPLAY_V27,
)

pytestmark = pytest.mark.unit


def _mutated(index: int, **changes: Any) -> tuple[WritePairReservation, ...]:
    return tuple(
        replace(item, **changes) if position == index else item
        for position, item in enumerate(V4_WRITE_PAIR_RESERVATIONS)
    )


def test_reservations_validate_and_span_23_to_26() -> None:
    validate_write_pair_reservations()
    assert V4_WRITE_PAIR_RESERVATIONS[0].event_schema == 23
    assert V4_WRITE_PAIR_RESERVATIONS[0].codec_version == "v21"
    assert V4_WRITE_PAIR_RESERVATIONS[-1].event_schema == 26
    assert V4_WRITE_PAIR_RESERVATIONS[-1].codec_version == "v24"
    assert len(V4_WRITE_PAIR_RESERVATIONS) == 4


def test_current_wire_maxima_are_unchanged() -> None:
    assert max(ACCEPTED_EVENT_SCHEMA_VERSIONS) == EVENT_SCHEMA_REPLAY_V27 == 27
    assert EVENT_SCHEMA_REPLAY_V22 == 22
    assert "v20" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v21" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v22" not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert hasattr(world.events, "EVENT_SCHEMA_REPLAY_V23")


def test_deepening_pair_is_separate_and_contiguous() -> None:
    validate_deepening_write_pairs()
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
    assert [item.event_schema for item in V4_DEEPENING_WRITE_PAIRS] == [27]
    assert [item.codec_version for item in V4_DEEPENING_WRITE_PAIRS] == ["v25"]
    assert TRAVEL_NETWORK_WRITE_PAIR_EVENT == 27
    assert TRAVEL_NETWORK_WRITE_PAIR_CODEC == "v25"
    reserved_events = {item.event_schema for item in V4_WRITE_PAIR_RESERVATIONS}
    reserved_codecs = {item.codec_version for item in V4_WRITE_PAIR_RESERVATIONS}
    assert reserved_events.isdisjoint(
        {item.event_schema for item in V4_DEEPENING_WRITE_PAIRS}
    )
    assert reserved_codecs.isdisjoint(
        {item.codec_version for item in V4_DEEPENING_WRITE_PAIRS}
    )


def test_deepening_pair_mutations_are_rejected() -> None:
    pair = V4_DEEPENING_WRITE_PAIRS[0]
    with pytest.raises(ValueError, match="v4_deepening_pair_overlap"):
        validate_deepening_write_pairs((replace(pair, event_schema=23),))
    with pytest.raises(ValueError, match="v4_deepening_pair_overlap"):
        validate_deepening_write_pairs((replace(pair, codec_version="v21"),))
    with pytest.raises(ValueError, match="v4_deepening_pair_noncontiguous_event"):
        validate_deepening_write_pairs(
            (pair, replace(pair, event_schema=29, codec_version="v27"))
        )
    with pytest.raises(ValueError, match="v4_deepening_pair_noncontiguous_codec"):
        validate_deepening_write_pairs(
            (pair, replace(pair, event_schema=28, codec_version="v27"))
        )
    with pytest.raises(ValueError, match="v4_deepening_pair_unknown_context"):
        validate_deepening_write_pairs(
            (replace(pair, context_id=cast(V4ContextId, "not_a_context")),)
        )
    with pytest.raises(ValueError, match="v4_deepening_pair_unowned_context"):
        validate_deepening_write_pairs(
            (replace(pair, context_id=V4ContextId.SOCIETAL_RESILIENCE),)
        )
    with pytest.raises(ValueError, match="v4_deepening_pair_unowned_context"):
        validate_deepening_write_pairs(
            (replace(pair, context_id=V4ContextId.SCIENCE),)
        )


def test_contexts_are_exactly_covered_and_disjoint() -> None:
    reserved = {item.context_id for item in V4_WRITE_PAIR_RESERVATIONS}
    assert not reserved & V4_EVENT_REUSING_CONTEXTS
    assert reserved | V4_EVENT_REUSING_CONTEXTS == {
        spec.context_id for spec in V4_CONTEXTS
    }
    assert V4ContextId.SOCIETAL_RESILIENCE in V4_EVENT_REUSING_CONTEXTS
    assert V4ContextId.SUPPLY_CHAINS in V4_EVENT_REUSING_CONTEXTS


def test_reservation_lookup_returns_the_declared_pair() -> None:
    assert reservation_for_context(V4ContextId.DISASTERS).event_schema == 26
    with pytest.raises(ValueError, match="v4_pair_unknown_context"):
        reservation_for_context(V4ContextId.SCIENCE)


def test_duplicate_and_gap_mutations_are_rejected() -> None:
    with pytest.raises(ValueError, match="v4_pair_duplicate_event"):
        validate_write_pair_reservations(_mutated(1, event_schema=23))
    with pytest.raises(ValueError, match="v4_pair_duplicate_codec"):
        validate_write_pair_reservations(_mutated(1, codec_version="v21"))
    with pytest.raises(ValueError, match="v4_pair_noncontiguous_event"):
        validate_write_pair_reservations(_mutated(1, event_schema=27))
    with pytest.raises(ValueError, match="v4_pair_noncontiguous_codec"):
        validate_write_pair_reservations(_mutated(1, codec_version="v25"))


def test_context_and_flag_mutations_are_rejected() -> None:
    with pytest.raises(ValueError, match="v4_pair_unknown_context"):
        validate_write_pair_reservations(_mutated(0, context_id="not_a_context"))
    with pytest.raises(ValueError, match="v4_pair_analysis_context"):
        validate_write_pair_reservations(
            _mutated(0, context_id=V4ContextId.SOCIETAL_RESILIENCE)
        )
    with pytest.raises(ValueError, match="v4_pair_unknown_flag"):
        validate_write_pair_reservations(_mutated(0, prerequisite_flags=("nope",)))


def test_coverage_and_overlap_mutations_are_rejected() -> None:
    with pytest.raises(ValueError, match="v4_pair_uncovered_context"):
        validate_write_pair_reservations(
            reusing_contexts=V4_EVENT_REUSING_CONTEXTS - {V4ContextId.SCIENCE}
        )
    with pytest.raises(ValueError, match="v4_pair_overlap"):
        validate_write_pair_reservations(
            reusing_contexts=V4_EVENT_REUSING_CONTEXTS | {V4ContextId.DISASTERS}
        )


def test_importing_the_module_emits_no_log_records(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import importlib

    import simulation.versioning

    with caplog.at_level(logging.DEBUG):
        importlib.reload(simulation.versioning)
    assert caplog.records == []
