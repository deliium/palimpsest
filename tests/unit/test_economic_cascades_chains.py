# mypy: ignore-errors
"""Dependency-conditioned chain linking and propagation summaries."""

from __future__ import annotations

import pytest

from analysis.economic_cascades_chains import link_economic_cascade_chains
from analysis.economic_cascades_contract import (
    CascadeAvailability,
    CascadeChainState,
    CascadeCoverage,
    CascadeDependencyKind,
    CascadeDisruptionKind,
)
from analysis.economic_cascades_detection import CascadeStageShortfall
from analysis.economic_cascades_policy import default_policy, policy_with
from analysis.economic_cascades_rows import (
    CascadeDependencyEdgeRow,
    CascadeDisruptionRow,
    CascadeEpisodeRow,
    CascadeStageRow,
)

pytestmark = pytest.mark.unit


def _episode(
    *,
    window: int = 0,
    kind: CascadeDisruptionKind = CascadeDisruptionKind.RESOURCE_LOSS,
) -> CascadeEpisodeRow:
    return CascadeEpisodeRow(
        window_index=window,
        window_tick=window * 32,
        kind=kind,
        disruption_count=1,
        magnitude_total=1,
        subject_count=1,
        first_sequence=0,
        last_sequence=0,
        coverage=CascadeCoverage.COMPLETE,
    )


def _disruption(
    subject: str,
    *,
    window: int = 0,
    kind: CascadeDisruptionKind = CascadeDisruptionKind.RESOURCE_LOSS,
) -> CascadeDisruptionRow:
    return CascadeDisruptionRow(
        window_index=window,
        window_tick=window * 32,
        sequence=0,
        kind=kind,
        subject_token=subject,
        magnitude_count=1,
        evidence_event_token=f"evt-{subject}-{window}",
        coverage=CascadeCoverage.COMPLETE,
    )


def _edge(
    upstream: str,
    downstream: str,
    *,
    kind: CascadeDependencyKind = CascadeDependencyKind.ITEM_INPUT,
    depth: int = 1,
    window: int = 0,
) -> CascadeDependencyEdgeRow:
    return CascadeDependencyEdgeRow(
        window_index=window,
        window_tick=window * 32,
        upstream_token=upstream,
        downstream_recipe_id=downstream,
        kind=kind,
        depth=depth,
        evidence_count=1,
    )


def _stage(
    recipe: str,
    *,
    window: int = 0,
    share: int = 500,
    output_kind: str = "material",
) -> CascadeStageShortfall:
    row = CascadeStageRow(
        window_index=window,
        window_tick=window * 32,
        recipe_id=recipe,
        action="craft",
        output_name=recipe,
        output_kind=output_kind,
        location_token="loc-1",
        demand_count=4,
        attempt_count=4,
        completion_count=2,
        tool_dependent=False,
        has_infrastructure=False,
        coverage=CascadeCoverage.COMPLETE,
    )
    return CascadeStageShortfall(
        stage=row,
        shortfall_share_milli=share,
        in_shortfall=share >= 250,
        availability=CascadeAvailability.AVAILABLE,
    )


def _mine_chain():
    episodes = [_episode()]
    disruptions = [_disruption("harvest_ore")]
    edges = [
        _edge("harvest_ore", "smelt_ore"),
        _edge("smelt_ore", "craft_tool"),
        _edge(
            "craft_tool",
            "harvest_grain",
            kind=CascadeDependencyKind.TOOL_DEPENDENCY,
        ),
    ]
    stages = [
        _stage("smelt_ore", window=0),
        _stage("craft_tool", window=0),
        _stage("harvest_grain", window=1, output_kind="food"),
    ]
    return episodes, disruptions, edges, stages


def test_four_step_mine_chain_links_along_real_edges() -> None:
    episodes, disruptions, edges, stages = _mine_chain()
    result = link_economic_cascade_chains(
        episodes=episodes,
        disruptions=disruptions,
        stages=stages,
        edges=edges,
    )
    linked = [
        row for row in result.chains if row.state is CascadeChainState.LINKED
    ]
    assert [
        (row.downstream_recipe_id, row.depth, row.lag_windows)
        for row in linked
    ] == [
        ("smelt_ore", 1, 0),
        ("craft_tool", 2, 0),
        ("harvest_grain", 3, 1),
    ]
    assert result.linked_count == 3
    assert result.max_depth == 3


def test_missing_intermediate_stage_is_unresolved() -> None:
    episodes, disruptions, edges, _stages = _mine_chain()
    result = link_economic_cascade_chains(
        episodes=episodes,
        disruptions=disruptions,
        stages=[],
        edges=edges,
    )
    assert result.linked_count == 0
    assert result.unresolved_count >= 1
    assert any(
        row.downstream_recipe_id == "smelt_ore"
        and row.state is CascadeChainState.UNRESOLVED
        for row in result.chains
    )


def test_shortfall_before_disruption_never_links() -> None:
    result = link_economic_cascade_chains(
        episodes=[_episode(window=1)],
        disruptions=[_disruption("harvest_ore", window=1)],
        stages=[_stage("smelt_ore", window=0)],
        edges=[_edge("harvest_ore", "smelt_ore")],
    )
    assert not any(
        row.state is CascadeChainState.LINKED for row in result.chains
    )
    assert any(
        row.state is CascadeChainState.UNRESOLVED for row in result.chains
    )


def test_route_closure_reaches_endpoint_stage() -> None:
    result = link_economic_cascade_chains(
        episodes=[_episode(kind=CascadeDisruptionKind.ROUTE_CLOSURE)],
        disruptions=[
            _disruption(
                "route:loc-a->loc-b", kind=CascadeDisruptionKind.ROUTE_CLOSURE
            )
        ],
        stages=[_stage("harvest_grain", share=400)],
        edges=[
            _edge(
                "route:loc-a->loc-b",
                "harvest_grain",
                kind=CascadeDependencyKind.TRANSPORT_DEPENDENCY,
            )
        ],
    )
    assert result.linked_count == 1
    assert result.chains[0].upstream_token == "route:loc-a->loc-b"


def test_infrastructure_destruction_reaches_mapped_stage() -> None:
    result = link_economic_cascade_chains(
        episodes=[
            _episode(kind=CascadeDisruptionKind.INFRASTRUCTURE_DESTRUCTION)
        ],
        disruptions=[
            _disruption(
                "asset:irrigation@loc-a",
                kind=CascadeDisruptionKind.INFRASTRUCTURE_DESTRUCTION,
            )
        ],
        stages=[_stage("harvest_grain", share=600)],
        edges=[
            _edge(
                "asset:irrigation@loc-a",
                "harvest_grain",
                kind=CascadeDependencyKind.INFRASTRUCTURE_DEPENDENCY,
            )
        ],
    )
    assert result.linked_count == 1


def test_population_loss_uses_a_labor_join() -> None:
    result = link_economic_cascade_chains(
        episodes=[_episode(kind=CascadeDisruptionKind.POPULATION_LOSS)],
        disruptions=[
            _disruption("body-1", kind=CascadeDisruptionKind.POPULATION_LOSS)
        ],
        stages=[_stage("smelt_ore", share=500)],
        edges=[_edge("harvest_ore", "smelt_ore")],
        labor_joins=(("body-1", ("harvest_ore",)),),
    )
    assert result.chains
    assert result.chains[0].upstream_token == "labor:harvest_ore"
    assert "body-1" not in {row.upstream_token for row in result.chains}


def test_population_loss_without_join_is_unresolved() -> None:
    result = link_economic_cascade_chains(
        episodes=[_episode(kind=CascadeDisruptionKind.POPULATION_LOSS)],
        disruptions=[
            _disruption("body-1", kind=CascadeDisruptionKind.POPULATION_LOSS)
        ],
        stages=[_stage("smelt_ore")],
        edges=[_edge("harvest_ore", "smelt_ore")],
    )
    assert result.linked_count == 0
    assert result.unresolved_count == 1
    assert "labor_join_missing" in result.notices


def test_depth_above_bound_is_excluded() -> None:
    recipe_ids = [f"r{index}" for index in range(1, 9)]
    edges = [
        _edge(recipe_ids[index], recipe_ids[index + 1])
        for index in range(len(recipe_ids) - 1)
    ]
    result = link_economic_cascade_chains(
        episodes=[_episode()],
        disruptions=[_disruption(recipe_ids[0])],
        stages=[_stage(recipe_ids[-1])],
        edges=edges,
    )
    assert all(row.depth <= 6 for row in result.chains)
    assert not any(
        row.downstream_recipe_id == recipe_ids[-1] for row in result.chains
    )


def test_lag_above_bound_is_not_linked() -> None:
    result = link_economic_cascade_chains(
        episodes=[_episode(window=0)],
        disruptions=[_disruption("harvest_ore", window=0)],
        stages=[_stage("smelt_ore", window=3)],
        edges=[_edge("harvest_ore", "smelt_ore")],
    )
    assert not any(
        row.state is CascadeChainState.LINKED for row in result.chains
    )
    assert all(row.lag_windows <= 2 for row in result.chains)


def test_three_linked_chains_make_availability() -> None:
    edges = [
        _edge("harvest_ore", "a"),
        _edge("harvest_ore", "b"),
        _edge("harvest_ore", "c"),
    ]
    stages = [_stage("a"), _stage("b"), _stage("c")]
    result = link_economic_cascade_chains(
        episodes=[_episode()],
        disruptions=[_disruption("harvest_ore")],
        stages=stages,
        edges=edges,
    )
    propagation = result.propagation_rows[0]
    assert propagation.linked_chain_count == 3
    assert propagation.availability is CascadeAvailability.AVAILABLE


def test_fewer_than_three_linked_chains_is_insufficient() -> None:
    result = link_economic_cascade_chains(
        episodes=[_episode()],
        disruptions=[_disruption("harvest_ore")],
        stages=[_stage("smelt_ore")],
        edges=[_edge("harvest_ore", "smelt_ore")],
    )
    assert result.propagation_rows[0].availability is (
        CascadeAvailability.INSUFFICIENT_SAMPLES
    )


def test_chain_tokens_are_deterministic() -> None:
    episodes, disruptions, edges, stages = _mine_chain()
    first = link_economic_cascade_chains(
        episodes=episodes,
        disruptions=disruptions,
        stages=stages,
        edges=edges,
    )
    second = link_economic_cascade_chains(
        episodes=episodes,
        disruptions=disruptions,
        stages=stages,
        edges=edges,
    )
    assert [row.chain_token for row in first.chains] == [
        row.chain_token for row in second.chains
    ]


def test_chain_cap_truncates_with_notice() -> None:
    episodes, disruptions, edges, stages = _mine_chain()
    result = link_economic_cascade_chains(
        episodes=episodes,
        disruptions=disruptions,
        stages=stages,
        edges=edges,
        policy=policy_with(max_chains=1),
    )
    assert len(result.chains) == 1
    assert "chains_truncated" in result.notices
    assert result.coverage is CascadeCoverage.PARTIAL


def test_propagation_rows_are_seeded_for_episodes_without_chains() -> None:
    result = link_economic_cascade_chains(
        episodes=[_episode()],
        disruptions=[_disruption("resource:node-1")],
        stages=[],
        edges=[],
    )
    assert len(result.propagation_rows) == 1
    row = result.propagation_rows[0]
    assert row.chain_count == 1
    assert row.unresolved_chain_count == 1
    assert row.availability is CascadeAvailability.UNAVAILABLE


def test_default_policy_is_used_when_omitted() -> None:
    episodes, disruptions, edges, stages = _mine_chain()
    result = link_economic_cascade_chains(
        episodes=episodes,
        disruptions=disruptions,
        stages=stages,
        edges=edges,
    )
    assert default_policy().min_linked_chains == 3
    assert result.chain_count == 3
