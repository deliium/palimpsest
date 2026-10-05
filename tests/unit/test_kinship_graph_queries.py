"""Pure kinship graph query and validation tests."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from world.kinship import (
    KinshipEdge,
    KinshipGraph,
    ancestors_of,
    children_of,
    descendants_of,
    establish_edge,
    siblings_of,
    stable_kinship_edge_id,
    validate_bootstrap_edges,
)


def _edge(parent: str, child: str, *, tick: int = 0) -> KinshipEdge:
    parent_id = AgentId(parent)
    child_id = AgentId(child)
    return KinshipEdge(
        parent_agent_id=parent_id,
        child_agent_id=child_id,
        established_tick=tick,
        edge_id=stable_kinship_edge_id(
            parent_agent_id=parent_id,
            child_agent_id=child_id,
            established_tick=tick,
        ),
    )


def _agents(*names: str) -> tuple[AgentId, ...]:
    return tuple(AgentId(name) for name in names)


def test_stable_edge_id_deterministic() -> None:
    a = AgentId("a")
    b = AgentId("b")
    first = stable_kinship_edge_id(
        parent_agent_id=a, child_agent_id=b, established_tick=0
    )
    second = stable_kinship_edge_id(
        parent_agent_id=a, child_agent_id=b, established_tick=0
    )
    assert first == second


def test_siblings_and_ancestors_depth_bound() -> None:
    graph = validate_bootstrap_edges(
        (
            _edge("p1", "c1"),
            _edge("p1", "c2"),
            _edge("p0", "p1"),
        ),
        registered_agent_ids=_agents("p0", "p1", "c1", "c2"),
        max_parents_per_child=2,
    )
    assert siblings_of(graph, AgentId("c1")) == (AgentId("c2"),)
    assert children_of(graph, AgentId("p1")) == (
        AgentId("c1"),
        AgentId("c2"),
    )
    ancestors = ancestors_of(
        graph,
        AgentId("c1"),
        max_depth=2,
        config_max_depth=8,
    )
    assert ancestors == (AgentId("p1"), AgentId("p0"))
    shallow = ancestors_of(
        graph,
        AgentId("c1"),
        max_depth=1,
        config_max_depth=8,
    )
    assert shallow == (AgentId("p1"),)
    descendants = descendants_of(
        graph,
        AgentId("p0"),
        max_depth=3,
        config_max_depth=8,
    )
    assert descendants == (
        AgentId("p1"),
        AgentId("c1"),
        AgentId("c2"),
    )


def test_rejects_cycle_and_duplicate() -> None:
    agents = _agents("a", "b", "c")
    graph = validate_bootstrap_edges(
        (_edge("a", "b"), _edge("b", "c")),
        registered_agent_ids=agents,
        max_parents_per_child=2,
    )
    with pytest.raises(ValueError, match="kinship_cycle_rejected"):
        establish_edge(
            graph,
            parent_agent_id=AgentId("c"),
            child_agent_id=AgentId("a"),
            established_tick=1,
            max_parents_per_child=2,
            known_agent_ids=agents,
        )
    with pytest.raises(ValueError, match="kinship_duplicate_edge"):
        validate_bootstrap_edges(
            (_edge("a", "b"), _edge("a", "b")),
            registered_agent_ids=agents,
            max_parents_per_child=2,
        )


def test_too_many_parents() -> None:
    agents = _agents("p1", "p2", "p3", "child")
    with pytest.raises(ValueError, match="kinship_too_many_parents"):
        validate_bootstrap_edges(
            (
                _edge("p1", "child"),
                _edge("p2", "child"),
                _edge("p3", "child"),
            ),
            registered_agent_ids=agents,
            max_parents_per_child=2,
        )
