"""Read-only analysis ports consume immutable events, exports, and memory evidence."""

from __future__ import annotations

import inspect

from analysis.contracts import (
    EventSource,
    ExportSource,
    MemoryEvidenceSource,
    ObjectiveEventSource,
)
from analysis.models import (
    ReconstructionEvidence,
    StructuredFactSet,
    SubjectiveDerivationEdge,
)
from analysis.sources import InMemoryMemoryEvidenceSource, InMemoryObjectiveEventSource
from memory.contracts import MemoryReconstructor
from memory.models import RecallEvidence
from simulation.contracts import make_export
from simulation.identifiers import derive_run_id
from simulation.models import SimulationExport, SimulationRunConfig
from world.events import Waited, WorldEvent, make_replayable_event
from world.identifiers import EventId, RequestId, WorldId, WorldRevision


class _FrozenSource:
    def __init__(self, export: SimulationExport) -> None:
        self._export = export

    def events(self) -> tuple[WorldEvent, ...]:
        return tuple(self._export.events)

    def export(self) -> SimulationExport:
        return self._export


def test_event_and_export_sources_are_read_only_snapshots() -> None:
    config = SimulationRunConfig(seed=3)
    run_id = derive_run_id(config)
    event = make_replayable_event(
        event_id=EventId("evt-1"),
        run_id=run_id.value,
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=RequestId("r-1"),
        resulting_revision=WorldRevision(2),
        details=Waited(),
        actor_id=None,
    )
    export = make_export(config, run_id, [event])
    source: EventSource = _FrozenSource(export)
    exports: ExportSource = _FrozenSource(export)
    assert source.events() == (event,)
    loaded = exports.export()
    assert loaded.metadata.seed == 3
    assert loaded.metadata.run_id == run_id
    assert loaded.events[0].details == Waited()
    assert isinstance(loaded.events, tuple)


def test_objective_and_memory_evidence_protocols_are_structural() -> None:
    event = make_replayable_event(
        event_id=EventId("evt-2"),
        run_id="run-a",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=RequestId("r-2"),
        resulting_revision=WorldRevision(1),
        details=Waited(),
        actor_id=None,
    )
    events: ObjectiveEventSource = InMemoryObjectiveEventSource([event])
    assert events.events_for_run("run-a") == (event,)
    assert events.event_by_id("run-a", EventId("evt-2")) is event
    assert events.event_by_id("run-a", EventId("missing")) is None

    memory: MemoryEvidenceSource = InMemoryMemoryEvidenceSource()
    assert memory.traces(run_id="run-a", owner_id="agent-1") == ()
    assert memory.reconstructions(run_id="run-a", owner_id="agent-1") == ()
    assert memory.derivation_edges(run_id="run-a", owner_id="agent-1") == ()


def test_analysis_dto_repr_omits_payload_content() -> None:
    facts = StructuredFactSet(
        concepts=frozenset({"secret-concept"}),
        entity_ids=frozenset({"ent-1"}),
        entity_labels=frozenset({"Alice"}),
        relations=frozenset({("saw", "a", "b")}),
        context_tags=frozenset({"night"}),
        location_id="loc-1",
        confidence=0.5,
        salience=0.2,
        narrative_fingerprint="abc",
        availability=__import__(
            "analysis.models", fromlist=["FactAvailability"]
        ).FactAvailability.PRESENT,
        projector_version="1",
    )
    text = repr(facts)
    assert "secret-concept" not in text
    assert "Alice" not in text
    assert "concept_count=1" in text

    evidence = ReconstructionEvidence(
        reconstruction_id="recon-1",
        run_id="run-1",
        owner_id="agent-1",
        source_memory_ids=("m-1",),
        concepts=("gate",),
        entity_ids=(),
        entity_labels=(),
        relations=(),
        context_tags=(),
        location_id=None,
        confidence=0.5,
        emotional_salience=0.1,
        generation=1,
        created_tick=3,
        policy_id="recall",
        policy_version="1",
        narrative_fingerprint=None,
        content_available=True,
    )
    assert "gate" not in repr(evidence)
    edge = SubjectiveDerivationEdge(
        derived_memory_id="m-2",
        source_memory_id="m-1",
        ordinal=0,
        reconstruction_id="recon-1",
    )
    assert "has_reconstruction=True" in repr(edge)


def test_memory_reconstructor_accepts_only_recall_evidence() -> None:
    signature = inspect.signature(MemoryReconstructor.reconstruct)
    params = list(signature.parameters.values())
    assert len(params) == 2  # self, evidence
    annotation = params[1].annotation
    assert annotation is RecallEvidence or annotation == "RecallEvidence"
    source = inspect.getsource(MemoryReconstructor)
    assert "WorldEvent" in source  # documented prohibition
    assert "RecallEvidence" in source
