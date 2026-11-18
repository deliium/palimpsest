# mypy: ignore-errors

"""Observer aliases stay coarse and never expose hidden instrument state."""

from __future__ import annotations

import json

import pytest

from observer.adapt import adapt_event
from observer.version import SEMANTIC_EVENT_TYPES, SEMANTIC_TYPE_BY_KIND
from tests.unit.test_measurement_serialization import _event

pytestmark = pytest.mark.unit


def test_measurement_events_alias_experiment_semantics() -> None:
    assert SEMANTIC_TYPE_BY_KIND["measurement_taken"] == "EXPERIMENT_RESOLVED"
    assert (
        SEMANTIC_TYPE_BY_KIND["instrument_calibrated"] == "EXPERIMENT_RESOLVED"
    )
    event = _event()
    adapted = adapt_event(event)
    assert adapted.type == "EXPERIMENT_RESOLVED"
    assert adapted.type in SEMANTIC_EVENT_TYPES
    import dataclasses

    payload = json.dumps(dataclasses.asdict(adapted), sort_keys=True)
    for hidden in (
        "intrinsic_bias",
        "correction",
        "base_error",
        "physical_value",
        "displayed_scalar",
        "displayed_category",
        "damage_milli",
        "instrument_before",
        "instrument_after",
    ):
        assert hidden not in payload
