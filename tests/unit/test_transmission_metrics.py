"""Transmission diffusion and rumor distortion metric tests."""

from __future__ import annotations

from analysis.models import (
    MetricAvailability,
    SocialTransmissionReport,
    TransmissionDistortion,
    TransmissionHopRecord,
)
from analysis.serialization import metric_document_fingerprint
from analysis.social_transmission import build_lineage_edges, detect_lineage_cycle
from analysis.transmission_metrics import (
    compute_knowledge_diffusion,
    compute_rumor_distortion,
)


def _hop(
    *,
    comm: str,
    root: str,
    hop: int,
    tick: int,
    speaker: str,
    listener: str,
    parent: str | None,
    stage: str,
    concepts: frozenset[str] | None = None,
    sender_c: float = 0.9,
    receiver_c: float | None = 0.7,
) -> TransmissionHopRecord:
    concepts = concepts or frozenset({"water"})
    return TransmissionHopRecord(
        communication_id=comm,
        event_id=f"evt-{comm}",
        speaker_id=speaker,
        listener_id=listener,
        action_kind="tell",
        hop_count=hop,
        tick=tick,
        sender_confidence=sender_c,
        receiver_confidence=receiver_c,
        transmission_root_id=root,
        concept_count=len(concepts),
        relation_count=0,
        parent_communication_id=parent,
        concepts=concepts,
        relations=frozenset(),
        adoption_stage=stage,
    )


def test_lineage_prefers_explicit_root_and_rejects_cycles() -> None:
    hops = (
        _hop(
            comm="c0",
            root="c0",
            hop=0,
            tick=1,
            speaker="a",
            listener="b",
            parent=None,
            stage="world_delivery",
            receiver_c=None,
        ),
        _hop(
            comm="c1",
            root="c0",
            hop=1,
            tick=2,
            speaker="b",
            listener="c",
            parent="c0",
            stage="receiver_trace",
        ),
    )
    edges = build_lineage_edges(hops)
    assert edges[1].parent_communication_id == "c0"
    assert not edges[1].unresolved
    assert detect_lineage_cycle(
        child_id="c0", parent_id="c1", parent_of={"c1": "c0", "c0": None}
    )


def test_knowledge_diffusion_reach_by_stage() -> None:
    hops = (
        _hop(
            comm="c0",
            root="c0",
            hop=0,
            tick=1,
            speaker="a",
            listener="b",
            parent=None,
            stage="world_delivery",
            receiver_c=None,
        ),
        _hop(
            comm="c0t",
            root="c0",
            hop=0,
            tick=1,
            speaker="a",
            listener="b",
            parent=None,
            stage="receiver_trace",
        ),
        _hop(
            comm="c1",
            root="c0",
            hop=1,
            tick=3,
            speaker="b",
            listener="c",
            parent="c0",
            stage="receiver_trace",
            concepts=frozenset({"water", "north"}),
        ),
    )
    doc = compute_knowledge_diffusion(
        hops,
        run_id="run-t",
        input_revision="rev-1",
        eligible_agent_ids=("a", "b", "c"),
    )
    assert doc.availability is MetricAvailability.PRESENT
    assert doc.values["root_count"] == 1
    assert doc.values["reach_world_delivery"] > 0.0
    assert doc.values["reach_receiver_trace"] > 0.0


def test_rumor_distortion_from_declared_parents() -> None:
    hops = (
        _hop(
            comm="c0",
            root="c0",
            hop=0,
            tick=1,
            speaker="a",
            listener="b",
            parent=None,
            stage="world_delivery",
            concepts=frozenset({"water"}),
            receiver_c=None,
        ),
        _hop(
            comm="c1",
            root="c0",
            hop=1,
            tick=2,
            speaker="b",
            listener="c",
            parent="c0",
            stage="receiver_trace",
            concepts=frozenset({"water", "north"}),
            receiver_c=0.4,
        ),
    )
    distortions = (
        TransmissionDistortion(
            from_communication_id="c0",
            to_communication_id="c1",
            concepts_added=1,
            concepts_removed=0,
            relations_added=0,
            relations_removed=0,
            cumulative_change=1,
        ),
    )
    report = SocialTransmissionReport(
        experiment_id="exp-1",
        run_id="run-t",
        metric_version="1",
        transmission_root_id="c0",
        hops=hops,
        distortions=distortions,
        unique_agent_count=3,
        branch_count=0,
        fan_out_count=1,
        max_hop_count=1,
        unresolved_link_count=0,
        event_count=1,
        trace_count=1,
    )
    doc = compute_rumor_distortion(report, run_id="run-t", input_revision="rev-1")
    assert doc.availability is MetricAvailability.PRESENT
    assert doc.values["mean_concepts_added"] == 1.0
    assert doc.values["distortion_edge_count"] == 1
    assert doc.values["mean_confidence_attenuation"] == 0.5


def test_transmission_metrics_permutation() -> None:
    hops = [
        _hop(
            comm="c0",
            root="c0",
            hop=0,
            tick=1,
            speaker="a",
            listener="b",
            parent=None,
            stage="world_delivery",
            receiver_c=None,
        ),
        _hop(
            comm="c1",
            root="c0",
            hop=1,
            tick=2,
            speaker="b",
            listener="c",
            parent="c0",
            stage="receiver_trace",
        ),
    ]
    first = compute_knowledge_diffusion(
        hops, run_id="run-t", input_revision="rev-1", eligible_agent_ids=("a", "b", "c")
    )
    second = compute_knowledge_diffusion(
        list(reversed(hops)),
        run_id="run-t",
        input_revision="rev-1",
        eligible_agent_ids=("c", "b", "a"),
    )
    assert metric_document_fingerprint(first) == metric_document_fingerprint(second)
