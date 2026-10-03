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
    assert type(doc.values["centralization_out"]) is float
    assert type(doc.values["mean_degree_centrality"]) is float
    assert type(doc.values["mean_betweenness_centrality"]) is float
    assert type(doc.values["mean_closeness_centrality"]) is float


def test_trust_network_reciprocal_dyad_centrality() -> None:
    rows = [
        RelationshipEdgeRow(
            source_id="a",
            target_id="b",
            logical_tick=1,
            activation_state="active",
            trust=0.9,
        ),
        RelationshipEdgeRow(
            source_id="b",
            target_id="a",
            logical_tick=1,
            activation_state="active",
            trust=0.9,
        ),
    ]
    doc = compute_trust_network_structure(
        rows, run_id="run-dyad", input_revision="rev-1", agent_ids=("a", "b")
    )
    assert doc.availability is MetricAvailability.PRESENT
    assert doc.values["reciprocity"] == 1.0
    assert doc.values["mean_degree_centrality"] == 1.0
    assert doc.values["mean_betweenness_centrality"] == 0.0
    assert type(doc.values["mean_closeness_centrality"]) is float
    assert type(doc.values["centralization_out"]) is float


def test_trust_network_star_centrality_present() -> None:
    hub = "hub"
    leaves = ("l1", "l2", "l3")
    rows: list[RelationshipEdgeRow] = []
    for leaf in leaves:
        rows.append(
            RelationshipEdgeRow(
                source_id=hub,
                target_id=leaf,
                logical_tick=1,
                activation_state="active",
                trust=0.8,
            )
        )
        rows.append(
            RelationshipEdgeRow(
                source_id=leaf,
                target_id=hub,
                logical_tick=1,
                activation_state="active",
                trust=0.5,
            )
        )
    doc = compute_trust_network_structure(
        rows,
        run_id="run-star",
        input_revision="rev-1",
        agent_ids=(hub, *leaves),
    )
    assert doc.availability is MetricAvailability.PRESENT
    assert doc.values["centralization_out"] is not None
    assert doc.values["mean_degree_centrality"] is not None
    assert doc.values["mean_betweenness_centrality"] is not None
    assert doc.values["mean_closeness_centrality"] is not None
    assert doc.values["mean_betweenness_centrality"] > 0.0


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
    assert "mean_degree_centrality" not in empty.values
    one = compute_trust_network_structure(
        [],
        run_id="run-n",
        input_revision="rev-1",
        agent_ids=("solo",),
    )
    assert one.values["node_count"] == 1
    assert one.values["density"] is None
    assert one.values["centralization_out"] is None
    assert one.values["mean_degree_centrality"] is None
    assert one.values["mean_betweenness_centrality"] is None
    assert one.values["mean_closeness_centrality"] is None
