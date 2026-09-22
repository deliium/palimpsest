"""Trust network and community metric tests."""

from __future__ import annotations

from analysis.models import MetricAvailability, RelationshipEdgeRow
from analysis.network_metrics import (
    build_signed_trust_digraph,
    canonicalize_community_labels,
    compute_group_community_structure,
    compute_trust_network_structure,
    nonnegative_undirected_projection,
)
from analysis.serialization import metric_document_fingerprint


def _rows() -> list[RelationshipEdgeRow]:
    return [
        RelationshipEdgeRow(
            source_id="a", target_id="b", logical_tick=1, activation_state="active", trust=0.8
        ),
        RelationshipEdgeRow(
            source_id="b", target_id="a", logical_tick=1, activation_state="active", trust=0.6
        ),
        RelationshipEdgeRow(
            source_id="b", target_id="c", logical_tick=2, activation_state="active", trust=0.4
        ),
        RelationshipEdgeRow(
            source_id="c", target_id="b", logical_tick=2, activation_state="active", trust=-0.9
        ),
        RelationshipEdgeRow(
            source_id="d", target_id="a", logical_tick=3, activation_state="active", trust=0.0
        ),
    ]


def test_signed_graph_drops_nonpositive_community_edges() -> None:
    digraph = build_signed_trust_digraph(_rows(), agent_ids=("a", "b", "c", "d"))
    assert digraph.number_of_nodes() == 4
    undirected = nonnegative_undirected_projection(digraph)
    assert undirected.has_edge("a", "b")
    assert undirected.has_edge("b", "c")
    # Negative c<-b does not add an undirected edge by itself; b->c positive does.
    assert not undirected.has_edge("c", "a")


def test_trust_network_structure_metrics() -> None:
    doc = compute_trust_network_structure(
        _rows(),
        run_id="run-n",
        input_revision="rev-1",
        agent_ids=("a", "b", "c", "d"),
    )
    assert doc.availability is MetricAvailability.PRESENT
    assert doc.values["node_count"] == 4
    assert doc.values["edge_count"] >= 3
    assert type(doc.values["density"]) is float
    assert type(doc.values["reciprocity"]) is float


def test_community_labels_canonical_and_permutation_stable() -> None:
    labels = canonicalize_community_labels(
        [frozenset({"c", "a"}), frozenset({"b"}), frozenset({"z", "m"})]
    )
    assert labels[0][0] == "a"
    first = compute_group_community_structure(
        _rows(), run_id="run-n", input_revision="rev-1", agent_ids=("a", "b", "c", "d")
    )
    second = compute_group_community_structure(
        list(reversed(_rows())),
        run_id="run-n",
        input_revision="rev-1",
        agent_ids=("d", "c", "b", "a"),
    )
    assert metric_document_fingerprint(first) == metric_document_fingerprint(second)
    assert first.values["community_count"] == second.values["community_count"]


def test_empty_and_one_node_network() -> None:
    empty = compute_trust_network_structure([], run_id="run-n", input_revision="rev-1")
    assert empty.availability is MetricAvailability.UNKNOWN
    one = compute_trust_network_structure(
        [],
        run_id="run-n",
        input_revision="rev-1",
        agent_ids=("solo",),
    )
    assert one.values["node_count"] == 1
    assert one.values["density"] is None
