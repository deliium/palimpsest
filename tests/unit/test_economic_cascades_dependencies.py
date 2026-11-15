# mypy: ignore-errors
"""Real recipe and topology dependency edges for economic cascades."""

from __future__ import annotations

import pytest

from analysis.economic_cascades_contract import (
    CascadeCoverage,
    CascadeDependencyKind,
    EconomicCascadesError,
)
from analysis.economic_cascades_dependencies import (
    INFRASTRUCTURE_STAGE_ACTIONS,
    build_economic_cascade_dependencies,
)
from analysis.economic_cascades_policy import policy_with
from analysis.supply_chain_contract import NONE_TOKEN
from analysis.supply_chain_events import (
    SupplyRecipeSpec,
    SupplyStageObservation,
)

pytestmark = pytest.mark.unit


def _recipe(
    recipe_id: str,
    *,
    action: str = "craft",
    resources: tuple[str, ...] = (),
    items: tuple[str, ...] = (),
    output: str,
    output_kind: str = "material",
    tool_role: str | None = None,
) -> SupplyRecipeSpec:
    return SupplyRecipeSpec(
        recipe_id=recipe_id,
        action=action,
        resource_input_names=resources,
        item_input_names=items,
        input_kinds=(),
        output_name=output,
        output_kind=output_kind,
        tool_role=tool_role,
    )


def _stage(
    recipe_id: str,
    *,
    window: int = 0,
    location: str = "loc-1",
    actor: str = "body-1",
    attempt: bool = True,
    completed: bool = False,
    sequence: int = 0,
) -> SupplyStageObservation:
    return SupplyStageObservation(
        tick=window * 32 + sequence,
        sequence=sequence,
        window_index=window,
        recipe_id=recipe_id,
        action="craft",
        location_token=location,
        actor_token=actor,
        item_names=(),
        completed=completed,
        attempt=attempt,
        started_success=True if attempt else None,
        duration_ticks=2,
        created_item_token=NONE_TOKEN,
        cause="craft",
    )


def _chain_recipes() -> tuple[SupplyRecipeSpec, ...]:
    return (
        _recipe("harvest_ore", action="harvest", resources=("ore",), output="ore"),
        _recipe("smelt_ore", items=("ore",), output="metal"),
        _recipe("craft_tool", items=("metal",), output="tool", output_kind="tool"),
        _recipe(
            "harvest_grain",
            action="harvest",
            resources=("grain",),
            output="grain",
            output_kind="food",
            tool_role="strike",
        ),
    )


def _edge(
    edges: tuple, upstream: str, downstream: str, kind: CascadeDependencyKind
):
    matches = [
        edge
        for edge in edges
        if edge.upstream_token == upstream
        and edge.downstream_recipe_id == downstream
        and edge.kind is kind
    ]
    assert matches, (upstream, downstream, kind)
    return matches[0]


def test_recipe_inputs_produce_real_edges() -> None:
    result = build_economic_cascade_dependencies(
        stages=[_stage("harvest_ore"), _stage("smelt_ore")],
        recipes=_chain_recipes(),
    )
    edge = _edge(
        result.edges,
        "harvest_ore",
        "smelt_ore",
        CascadeDependencyKind.ITEM_INPUT,
    )
    assert edge.depth == 2
    _edge(
        result.edges,
        "smelt_ore",
        "craft_tool",
        CascadeDependencyKind.ITEM_INPUT,
    )
    _edge(
        result.edges,
        "craft_tool",
        "harvest_grain",
        CascadeDependencyKind.TOOL_DEPENDENCY,
    )
    assert result.coverage is CascadeCoverage.COMPLETE


def test_resource_input_edges_use_producer_output_names() -> None:
    recipes = (
        _recipe("produce_grain", action="harvest", output="grain", output_kind="food"),
        _recipe(
            "harvest_wheat",
            action="harvest",
            resources=("grain",),
            output="wheat",
            output_kind="food",
        ),
    )
    result = build_economic_cascade_dependencies(
        stages=[_stage("produce_grain"), _stage("harvest_wheat")],
        recipes=recipes,
    )
    _edge(
        result.edges,
        "produce_grain",
        "harvest_wheat",
        CascadeDependencyKind.RESOURCE_INPUT,
    )


def test_unknown_input_name_creates_no_edge() -> None:
    recipes = (_recipe("mill", items=("missing",), output="flour"),)
    result = build_economic_cascade_dependencies(
        stages=[_stage("mill")], recipes=recipes
    )
    assert result.edges == ()


def test_stage_demand_includes_downstream_attempts() -> None:
    recipes = (
        _recipe("harvest_ore", action="harvest", resources=("ore",), output="ore"),
        _recipe("smelt_ore", items=("ore",), output="metal"),
    )
    stages = [
        _stage("harvest_ore", attempt=True, completed=True),
        _stage("smelt_ore", attempt=True, sequence=1),
        _stage("smelt_ore", attempt=True, sequence=2),
    ]
    result = build_economic_cascade_dependencies(stages=stages, recipes=recipes)
    row = next(row for row in result.stage_rows if row.recipe_id == "harvest_ore")
    assert row.demand_count == 3
    assert row.attempt_count == 1
    assert row.completion_count == 1


def test_stage_tool_dependence_and_infrastructure_presence() -> None:
    recipes = (
        _recipe(
            "harvest_grain",
            action="harvest",
            resources=("grain",),
            output="grain",
            output_kind="food",
            tool_role="strike",
        ),
    )
    result = build_economic_cascade_dependencies(
        stages=[_stage("harvest_grain", location="loc-1")],
        recipes=recipes,
        infrastructure=(("loc-1", "irrigation", True),),
    )
    row = result.stage_rows[0]
    assert row.tool_dependent is True
    assert row.has_infrastructure is True
    assert INFRASTRUCTURE_STAGE_ACTIONS["irrigation"] == frozenset({"harvest"})
    _edge(
        result.edges,
        "asset:irrigation@loc-1",
        "harvest_grain",
        CascadeDependencyKind.INFRASTRUCTURE_DEPENDENCY,
    )


def test_destroyed_infrastructure_has_no_edge() -> None:
    recipes = (_recipe("harvest_grain", action="harvest", output="grain"),)
    result = build_economic_cascade_dependencies(
        stages=[_stage("harvest_grain", location="loc-1")],
        recipes=recipes,
        infrastructure=(("loc-1", "irrigation", False),),
    )
    assert not any(
        edge.kind is CascadeDependencyKind.INFRASTRUCTURE_DEPENDENCY
        for edge in result.edges
    )
    assert result.stage_rows[0].has_infrastructure is False


def test_non_open_route_creates_a_transport_dependency() -> None:
    recipes = (_recipe("harvest_grain", action="harvest", output="grain"),)
    closed = build_economic_cascade_dependencies(
        stages=[_stage("harvest_grain", location="loc-a")],
        recipes=recipes,
        routes=(("loc-a", "loc-b", "closed"),),
    )
    _edge(
        closed.edges,
        "route:loc-a->loc-b",
        "harvest_grain",
        CascadeDependencyKind.TRANSPORT_DEPENDENCY,
    )
    open_route = build_economic_cascade_dependencies(
        stages=[_stage("harvest_grain", location="loc-a")],
        recipes=recipes,
        routes=(("loc-a", "loc-b", "open"),),
    )
    assert not any(
        edge.kind is CascadeDependencyKind.TRANSPORT_DEPENDENCY
        for edge in open_route.edges
    )


def test_labor_joins_are_sorted_and_not_edges() -> None:
    recipes = (
        _recipe("harvest_ore", action="harvest", resources=("ore",), output="ore"),
        _recipe("smelt_ore", items=("ore",), output="metal"),
    )
    stages = [
        _stage("harvest_ore", actor="body-b", completed=True),
        _stage("smelt_ore", actor="body-a", completed=True, sequence=1),
        _stage("smelt_ore", actor="body-a", completed=False, sequence=2),
    ]
    result = build_economic_cascade_dependencies(stages=stages, recipes=recipes)
    assert result.labor_joins == (
        ("body-a", ("smelt_ore",)),
        ("body-b", ("harvest_ore",)),
    )
    assert all(
        "body-a" not in edge.upstream_token for edge in result.edges
    )


def test_depth_bound_drops_deeper_edges() -> None:
    recipes = (
        _recipe("r1", action="harvest", output="n1"),
        _recipe("r2", items=("n1",), output="n2"),
        _recipe("r3", items=("n2",), output="n3"),
        _recipe("r4", items=("n3",), output="n4"),
        _recipe("r5", items=("n4",), output="n5"),
        _recipe("r6", items=("n5",), output="n6"),
        _recipe("r7", items=("n6",), output="n7"),
    )
    stages = [_stage(f"r{index}") for index in range(1, 8)]
    result = build_economic_cascade_dependencies(stages=stages, recipes=recipes)
    assert result.max_depth <= 6
    assert "dependency_depth_truncated" in result.notices
    assert not any(
        edge.downstream_recipe_id == "r7" for edge in result.edges
    )


def test_cycle_is_rejected() -> None:
    recipes = (
        _recipe("a", items=("b",), output="a"),
        _recipe("b", items=("a",), output="b"),
    )
    with pytest.raises(EconomicCascadesError):
        build_economic_cascade_dependencies(
            stages=[_stage("a"), _stage("b")], recipes=recipes
        )


def test_complete_graph_validation_is_opt_in() -> None:
    recipes = (_recipe("mill", items=("missing",), output="flour"),)
    build_economic_cascade_dependencies(stages=[_stage("mill")], recipes=recipes)
    with pytest.raises(EconomicCascadesError):
        build_economic_cascade_dependencies(
            stages=[_stage("mill")],
            recipes=recipes,
            require_complete_graph=True,
        )


def test_stage_and_edge_caps_truncate_deterministically() -> None:
    recipes = (
        _recipe("harvest_ore", action="harvest", resources=("ore",), output="ore"),
        _recipe("smelt_ore", items=("ore",), output="metal"),
        _recipe("forge_ore", items=("ore",), output="ingot"),
    )
    stages = [
        _stage("harvest_ore", location=f"loc-{index}") for index in range(5)
    ]
    result = build_economic_cascade_dependencies(
        stages=stages,
        recipes=recipes,
        policy=policy_with(max_stages=2, max_dependency_edges=1),
    )
    assert len(result.stage_rows) == 2
    assert len(result.edges) == 1
    assert "stages_truncated" in result.notices
    assert "edges_truncated" in result.notices
    assert result.coverage is CascadeCoverage.PARTIAL


def test_empty_evidence_is_missing_coverage() -> None:
    result = build_economic_cascade_dependencies(stages=[], recipes=())
    assert result.stage_rows == ()
    assert result.edges == ()
    assert result.coverage is CascadeCoverage.MISSING


def test_edges_are_repeated_for_observed_windows() -> None:
    recipes = (
        _recipe("harvest_ore", action="harvest", resources=("ore",), output="ore"),
        _recipe("smelt_ore", items=("ore",), output="metal"),
    )
    stages = [
        _stage("harvest_ore", window=0),
        _stage("smelt_ore", window=0, sequence=1),
        _stage("harvest_ore", window=1, sequence=2),
        _stage("smelt_ore", window=1, sequence=3),
    ]
    result = build_economic_cascade_dependencies(stages=stages, recipes=recipes)
    windows = {
        edge.window_index
        for edge in result.edges
        if edge.upstream_token == "harvest_ore"
        and edge.downstream_recipe_id == "smelt_ore"
    }
    assert windows == {0, 1}
