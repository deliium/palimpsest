# mypy: ignore-errors

"""Blank-slate measurement probes count real content, not default objects."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition.measurement import (
    MeasurementEvidence,
    MeasurementLedger,
    empty_measurement_ledger,
)
from agents.models import AgentId
from simulation.new_agent_initialization import (
    BLANK_SLATE_SUBJECTIVE_STORES,
    SUBJECTIVE_COPY_DENY_LIST,
)
from simulation.runner import _blank_slate_counts
from world.identifiers import EntityId
from world.measurement import MeasurementQuantity, MeasurementUnit, MeasurementUnitKind

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-1")
_TOOL = EntityId("item-thermometer")


def _loop(ledger: object | None) -> object:
    return SimpleNamespace(
        replication_ledger_if_present=lambda: None,
        measurement_ledger_if_present=lambda: ledger,
    )


def _populated() -> MeasurementLedger:
    rows = tuple(
        MeasurementEvidence(
            evidence_id=f"mev:{index:032d}",
            owner_id=_OWNER,
            instrument_id=_TOOL,
            target_id=EntityId("loc-1"),
            quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
            unit=MeasurementUnit(MeasurementUnitKind.CELSIUS),
            value_kind="scalar",
            displayed_scalar_milli=15000,
            displayed_category=None,
            nominal_division_milli=1000,
            observed_tick=index,
            source_kind="own_observation",
            source_event_id=f"event-{index}",
            delivery_event_id=None,
            declared_root=f"event-{index}",
        )
        for index in range(3)
    )
    return MeasurementLedger(
        owner_id=_OWNER,
        evidence=rows,
        beliefs=(),
        revisions=(),
        receipts=tuple(
            f"own:{row.source_event_id}" for row in rows
        ),
        notices=(),
    )


def test_store_registries_include_measurement() -> None:
    assert "measurement_ledger" in BLANK_SLATE_SUBJECTIVE_STORES
    assert "measurement_ledger" in SUBJECTIVE_COPY_DENY_LIST


def test_empty_enabled_ledger_counts_zero() -> None:
    counts = _blank_slate_counts(_loop(empty_measurement_ledger(_OWNER)))
    assert counts.measurement_ledger == 0


def test_measurement_content_counts_without_replication_state() -> None:
    counts = _blank_slate_counts(_loop(_populated()))
    assert counts.measurement_ledger > 0
    assert counts.replication_ledger == 0


def test_absent_ledger_is_not_known_empty_content() -> None:
    counts = _blank_slate_counts(_loop(None))
    assert counts.measurement_ledger == 0
