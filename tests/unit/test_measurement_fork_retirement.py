# mypy: ignore-errors

"""Owner-ordered measurement export and fork/retirement isolation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition.measurement import empty_measurement_ledger
from agents.models import AgentId
from simulation.runner import SimulationRunner

pytestmark = pytest.mark.unit


def _checkpoint(owner: str):
    return SimpleNamespace(
        measurement_ledger=empty_measurement_ledger(AgentId(owner))
    )


def test_export_includes_active_then_retired_owners_without_aliasing() -> None:
    active = SimpleNamespace(
        export_runtime_checkpoint=lambda: _checkpoint("agent-active"),
        retired_record=None,
    )
    retired = SimpleNamespace(
        export_runtime_checkpoint=lambda: SimpleNamespace(measurement_ledger=None),
        retired_record=SimpleNamespace(
            runtime_checkpoint=_checkpoint("agent-retired")
        ),
    )
    stub = SimpleNamespace(_runtimes=(active, retired))
    first = SimulationRunner.export_measurement_ledgers(stub)
    second = SimulationRunner.export_measurement_ledgers(stub)
    assert [ledger.owner_id.value for ledger in first] == [
        "agent-active",
        "agent-retired",
    ]
    assert first == second
    assert first is not second


def test_missing_owner_capture_is_not_reconstructed() -> None:
    stub = SimpleNamespace(
        _runtimes=(
            SimpleNamespace(
                export_runtime_checkpoint=lambda: SimpleNamespace(
                    measurement_ledger=None
                ),
                retired_record=None,
            ),
        )
    )
    assert SimulationRunner.export_measurement_ledgers(stub) == ()


def test_restore_rejects_a_foreign_owner_ledger() -> None:
    from agents.cognition.loop import CognitiveLoop
    from agents.cognition.measurement import MeasurementLedger

    assert MeasurementLedger is not None
    loop = object.__new__(CognitiveLoop)
    loop._measurement_ledger = None
    loop._measurement_enabled = False
    with pytest.raises(ValueError, match="owner mismatch"):
        loop.restore_measurement_ledger(
            empty_measurement_ledger(AgentId("agent-other")),
            AgentId("agent-self"),
        )
