"""Read-only analysis ports consume immutable events and exports."""

from __future__ import annotations

from analysis.contracts import EventSource, ExportSource
from simulation.contracts import make_export
from simulation.identifiers import derive_run_id
from simulation.models import SimulationExport, SimulationRunConfig
from world.events import WorldEvent
from world.identifiers import EventId, WorldRevision


class _FrozenSource:
    def __init__(self, export: SimulationExport) -> None:
        self._export = export

    def events(self) -> tuple[WorldEvent, ...]:
        return self._export.events

    def export(self) -> SimulationExport:
        return self._export


def test_event_and_export_sources_are_read_only_snapshots() -> None:
    config = SimulationRunConfig(seed=3)
    run_id = derive_run_id(config)
    event = WorldEvent(
        event_id=EventId("evt-1"),
        revision=WorldRevision(2),
        kind="observed",
        payload={"n": 1},
    )
    export = make_export(config, run_id, [event])
    source: EventSource = _FrozenSource(export)
    exports: ExportSource = _FrozenSource(export)
    assert source.events() == (event,)
    loaded = exports.export()
    assert loaded.metadata.seed == 3
    assert loaded.metadata.run_id == run_id
    assert loaded.events[0].payload["n"] == 1
    assert "WorldState" not in type(loaded).__module__
