# mypy: ignore-errors

"""Observed supply dependency graph and bounded chain paths."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from analysis.supply_chain_contract import (
    SupplyCoverage,
    SupplyEdgeKind,
    SupplyNodeKind,
    analysis_supply_token,
)
from analysis.supply_chain_events import (
    SupplyOrganizationClaim,
    SupplyRecipeSpec,
    SupplySkillLevel,
    supply_evidence_from_events,
)
from analysis.supply_chain_graph import (
    SupplyDependencyEdge,
    SupplyDependencyGraph,
    _build_chain_paths,
    build_dependency_graph,
)
from analysis.supply_chain_policy import (
    SupplyChainAnalysisPolicy,
    default_supply_chain_analysis_policy,
)
from world.effects import ActionCause
from world.events import (
    CraftStarted,
    ItemCrafted,
    ItemStored,
    OccurrenceContext,
    ResourceHarvested,
    StructureBuilt,
    WorldEvent,
    target_id_for_details,
)
from world.identifiers import (
    EntityId,
    EventId,
    RecipeId,
    RequestId,
    WorldId,
    WorldRevision,
)

pytestmark = pytest.mark.unit

_WORLD = WorldId("world-supply-graph")


def _recipe(
    recipe_id: str,
    action: str,
    *,
    resources: tuple[str, ...] = (),
    items: tuple[str, ...] = (),
    output: str,
    output_kind: str = "material",
    skill: str | None = None,
    tool: str | None = None,
) -> SupplyRecipeSpec:
    return SupplyRecipeSpec(
        recipe_id=recipe_id,
        action=action,
        resource_input_names=resources,
        item_input_names=items,
        input_kinds=(),
        output_name=output,
        output_kind=output_kind,
        skill_domain=skill,
        tool_role=tool,
    )


_HARVEST_GRAIN = _recipe(
    "harvest_grain", "harvest", resources=("grain",), output="grain", output_kind="food"
)
_HARVEST_WOOD = _recipe("harvest_wood", "harvest", resources=("wood",), output="wood")
_HARVEST_BREAD = _recipe(
    "harvest_bread", "harvest", resources=("bread",), output="bread", output_kind="food"
)
_MILL = _recipe("mill_grain", "craft", items=("grain",), output="flour")
_BAKE = _recipe(
    "bake_bread", "craft", items=("flour",), output="bread", output_kind="food"
)
_BUILD = _recipe(
    "build_shelter",
    "build",
    items=("wood",),
    output="shelter",
    output_kind="structure",
)
_STORE = _recipe(
    "store_food", "store", items=("bread",), output="store", output_kind="storage"
)
_TOOL = _recipe(
    "assemble_tool",
    "craft",
    items=("flour",),
    output="fine_tool",
    output_kind="tool",
    skill="crafting",
    tool="strike",
)
_RECIPES = (
    _HARVEST_GRAIN,
    _HARVEST_WOOD,
    _HARVEST_BREAD,
    _MILL,
    _BAKE,
    _BUILD,
    _STORE,
    _TOOL,
)


def _event(
    details: object,
    *,
    tick: int,
    sequence: int,
    event_id: str,
    actor: str = "body-1",
    location: str = "loc-1",
) -> WorldEvent:
    request = RequestId(f"req-{event_id}")
    return WorldEvent(
        event_id=EventId(event_id),
        run_id="run-supply-graph",
        world_id=_WORLD,
        tick=tick,
        sequence=sequence,
        request_id=request,
        resulting_revision=WorldRevision(tick),
        schema_version=6,
        details=details,  # type: ignore[arg-type]
        actor_id=EntityId(actor),
        target_id=target_id_for_details(details),  # type: ignore[arg-type]
        cause=ActionCause(request, EntityId(actor)),
        occurrence=OccurrenceContext(origin_location_id=EntityId(location)),
    )


def _harvest(
    recipe_id: str,
    created: str,
    *,
    tick: int = 0,
    event_id: str = "evt-harvest",
    sequence: int = 0,
    location: str = "loc-1",
    success: bool = True,
) -> WorldEvent:
    return _event(
        ResourceHarvested(
            RecipeId(recipe_id),
            EntityId(f"res-{recipe_id}"),
            success,
            1,
            2.0,
            created_item_id=EntityId(created) if success else None,
        ),
        tick=tick,
        sequence=sequence,
        event_id=event_id,
        location=location,
    )


def _craft_start(
    recipe_id: str,
    consumed: tuple[str, ...],
    *,
    tick: int,
    event_id: str,
    location: str = "loc-1",
) -> WorldEvent:
    return _event(
        CraftStarted(
            RecipeId(recipe_id),
            True,
            1,
            consumed_item_ids=tuple(EntityId(value) for value in consumed),
        ),
        tick=tick,
        sequence=0,
        event_id=event_id,
        location=location,
    )


def _craft_done(
    recipe_id: str,
    created: str,
    *,
    tick: int,
    event_id: str,
    location: str = "loc-1",
) -> WorldEvent:
    return _event(
        ItemCrafted(RecipeId(recipe_id), EntityId(created), EntityId("body-1"), 1),
        tick=tick,
        sequence=0,
        event_id=event_id,
        location=location,
    )


def _evidence(events, **kwargs):
    return supply_evidence_from_events(
        tuple(events),
        policy=kwargs.pop("policy", default_supply_chain_analysis_policy()),
        recipes=kwargs.pop("recipes", _RECIPES),
        **kwargs,
    )


def _edge_kinds(graph: SupplyDependencyGraph) -> set[SupplyEdgeKind]:
    return {edge.edge_kind for edge in graph.edges}


def test_harvest_emits_resource_to_item() -> None:
    graph = build_dependency_graph(
        _evidence([_harvest("harvest_grain", "item-grain")]),
        policy=default_supply_chain_analysis_policy(),
    )
    assert SupplyEdgeKind.RESOURCE_TO_ITEM in _edge_kinds(graph)
    resource = next(
        edge
        for edge in graph.edges
        if edge.edge_kind is SupplyEdgeKind.RESOURCE_TO_ITEM
    )
    assert (resource.from_token, resource.to_token) == ("grain", "grain")


def test_craft_emits_input_to_output_edges() -> None:
    graph = build_dependency_graph(
        _evidence(
            [
                _harvest("harvest_grain", "item-grain", tick=0),
                _craft_start(
                    "mill_grain", ("item-grain",), tick=0, event_id="evt-start"
                ),
                _craft_done("mill_grain", "item-flour", tick=1, event_id="evt-done"),
            ]
        ),
        policy=default_supply_chain_analysis_policy(),
    )
    edge = next(
        edge for edge in graph.edges if edge.edge_kind is SupplyEdgeKind.ITEM_TO_ITEM
    )
    assert (edge.from_token, edge.to_token) == ("grain", "flour")


def test_attempt_only_rows_emit_no_edge() -> None:
    graph = build_dependency_graph(
        _evidence([_harvest("harvest_grain", "item-grain", success=False)]),
        policy=default_supply_chain_analysis_policy(),
    )
    assert graph.edges == ()


def test_structure_and_storage_edges() -> None:
    built = _event(
        StructureBuilt(
            RecipeId("build_shelter"),
            EntityId("structure-1"),
            EntityId("loc-1"),
            0.75,
            1,
            EntityId("item-wood"),
        ),
        tick=1,
        sequence=0,
        event_id="evt-build",
    )
    stored = _event(
        ItemStored(
            RecipeId("store_food"),
            EntityId("structure-2"),
            1,
            1,
            EntityId("item-bread"),
        ),
        tick=2,
        sequence=0,
        event_id="evt-store",
    )
    graph = build_dependency_graph(
        _evidence(
            [
                _harvest("harvest_wood", "item-wood", tick=0),
                built,
                _harvest("harvest_bread", "item-bread", tick=0, event_id="evt-bread"),
                stored,
            ]
        ),
        policy=default_supply_chain_analysis_policy(),
    )
    assert SupplyEdgeKind.ITEM_TO_STRUCTURE in _edge_kinds(graph)
    assert SupplyEdgeKind.ITEM_TO_STORAGE in _edge_kinds(graph)


def test_transport_edge_uses_creation_location() -> None:
    graph = build_dependency_graph(
        _evidence(
            [
                _harvest("harvest_grain", "item-grain", tick=0, location="loc-1"),
                _craft_start(
                    "mill_grain",
                    ("item-grain",),
                    tick=0,
                    event_id="evt-start",
                    location="loc-2",
                ),
                _craft_done(
                    "mill_grain",
                    "item-flour",
                    tick=1,
                    event_id="evt-done",
                    location="loc-2",
                ),
            ]
        ),
        policy=default_supply_chain_analysis_policy(),
    )
    transport = next(
        edge for edge in graph.edges if edge.edge_kind is SupplyEdgeKind.TRANSPORT
    )
    assert transport.created_elsewhere_count == 1


def test_location_edge_for_each_completed_row() -> None:
    graph = build_dependency_graph(
        _evidence([_harvest("harvest_grain", "item-grain")]),
        policy=default_supply_chain_analysis_policy(),
    )
    edges = [
        edge
        for edge in graph.edges
        if edge.edge_kind is SupplyEdgeKind.LOCATION_TO_STAGE
    ]
    assert len(edges) == 1
    assert graph.locations[0].location_token == "loc-1"


def test_infrastructure_edge_requires_coverage() -> None:
    evidence = _evidence(
        [_harvest("harvest_grain", "item-grain")],
        infrastructure=[
            SimpleNamespace(
                location_token="loc-1", kinds=("well",), status="operational"
            )
        ],
    )
    graph = build_dependency_graph(
        evidence, policy=default_supply_chain_analysis_policy()
    )
    assert SupplyEdgeKind.INFRASTRUCTURE_TO_STAGE in _edge_kinds(graph)

    without = build_dependency_graph(
        _evidence([_harvest("harvest_grain", "item-grain")]),
        policy=default_supply_chain_analysis_policy(),
    )
    assert SupplyEdgeKind.INFRASTRUCTURE_TO_STAGE not in _edge_kinds(without)


def test_organization_edge_joins_actor_tokens() -> None:
    claim = SupplyOrganizationClaim(
        organization_token="org-1",
        command_kinds=("harvest",),
        actor_tokens=("body-1",),
        first_tick=0,
        last_tick=0,
        claim_count=1,
    )
    graph = build_dependency_graph(
        _evidence(
            [_harvest("harvest_grain", "item-grain")], organization_claims=[claim]
        ),
        policy=default_supply_chain_analysis_policy(),
    )
    assert SupplyEdgeKind.ORGANIZATION_TO_STAGE in _edge_kinds(graph)


def test_organization_edge_absent_when_actor_unclaimed() -> None:
    claim = SupplyOrganizationClaim(
        organization_token="org-1",
        command_kinds=("harvest",),
        actor_tokens=("body-2",),
        first_tick=0,
        last_tick=0,
        claim_count=1,
    )
    graph = build_dependency_graph(
        _evidence(
            [_harvest("harvest_grain", "item-grain")], organization_claims=[claim]
        ),
        policy=default_supply_chain_analysis_policy(),
    )
    assert SupplyEdgeKind.ORGANIZATION_TO_STAGE not in _edge_kinds(graph)


def test_tool_edge_for_tool_recipe() -> None:
    graph = build_dependency_graph(
        _evidence(
            [
                _harvest("harvest_grain", "item-flour", tick=0),
                _craft_start(
                    "assemble_tool", ("item-flour",), tick=0, event_id="evt-start"
                ),
                _craft_done("assemble_tool", "item-tool", tick=1, event_id="evt-done"),
            ]
        ),
        policy=default_supply_chain_analysis_policy(),
    )
    assert SupplyEdgeKind.TOOL_TO_STAGE in _edge_kinds(graph)


def test_skill_edge_requires_levels() -> None:
    graph = build_dependency_graph(
        _evidence(
            [
                _harvest("harvest_grain", "item-flour", tick=0),
                _craft_start(
                    "assemble_tool", ("item-flour",), tick=0, event_id="evt-start"
                ),
                _craft_done("assemble_tool", "item-tool", tick=1, event_id="evt-done"),
            ]
        ),
        policy=default_supply_chain_analysis_policy(),
    )
    assert SupplyEdgeKind.SKILL_TO_STAGE not in _edge_kinds(graph)

    with_skill = build_dependency_graph(
        _evidence(
            [
                _harvest("harvest_grain", "item-flour", tick=0),
                _craft_start(
                    "assemble_tool", ("item-flour",), tick=0, event_id="evt-start"
                ),
                _craft_done("assemble_tool", "item-tool", tick=1, event_id="evt-done"),
            ],
            skill_levels=[SupplySkillLevel("body-1", "crafting", 0.5)],
        ),
        policy=default_supply_chain_analysis_policy(),
    )
    assert SupplyEdgeKind.SKILL_TO_STAGE in _edge_kinds(with_skill)


def test_share_milli_is_floor() -> None:
    events = [
        _harvest("harvest_grain", "item-grain", tick=0, event_id="evt-1"),
        _harvest("harvest_grain", "item-grain", tick=1, event_id="evt-2"),
        _harvest(
            "harvest_grain", "item-grain", tick=2, event_id="evt-3", success=False
        ),
    ]
    graph = build_dependency_graph(
        _evidence(events), policy=default_supply_chain_analysis_policy()
    )
    edge = next(
        edge
        for edge in graph.edges
        if edge.edge_kind is SupplyEdgeKind.RESOURCE_TO_ITEM
    )
    assert edge.observed_count == 3
    assert edge.completed_count == 2
    assert edge.share_milli == 666


def test_chain_requires_two_stages() -> None:
    graph = build_dependency_graph(
        _evidence(
            [
                _harvest("harvest_grain", "item-grain", tick=0),
                _craft_start(
                    "mill_grain", ("item-grain",), tick=0, event_id="evt-start"
                ),
                _craft_done("mill_grain", "item-flour", tick=1, event_id="evt-done"),
            ]
        ),
        policy=default_supply_chain_analysis_policy(),
    )
    assert graph.chains
    chain = graph.chains[0]
    assert chain.depth == 2
    assert chain.stage_tokens == ("grain", "flour")


def test_chain_tokens_are_deterministic() -> None:
    def build() -> SupplyDependencyGraph:
        return build_dependency_graph(
            _evidence(
                [
                    _harvest("harvest_grain", "item-grain", tick=0),
                    _craft_start(
                        "mill_grain", ("item-grain",), tick=0, event_id="evt-start"
                    ),
                    _craft_done(
                        "mill_grain", "item-flour", tick=1, event_id="evt-done"
                    ),
                ]
            ),
            policy=default_supply_chain_analysis_policy(),
        )

    first = build()
    second = build()
    assert [chain.chain_token for chain in first.chains] == [
        chain.chain_token for chain in second.chains
    ]
    assert first.chains[0].chain_token == analysis_supply_token(
        "sc-chain-", "|".join(first.chains[0].edge_tokens)
    )


def test_chain_depth_is_capped() -> None:
    edges = []
    for index in range(9):
        edges.append(
            SupplyDependencyEdge(
                edge_token=analysis_supply_token("sc-edge-", f"e{index}"),
                window_index=0,
                from_kind=SupplyNodeKind.ITEM,
                from_token=f"n{index}",
                to_kind=SupplyNodeKind.ITEM,
                to_token=f"n{index + 1}",
                edge_kind=SupplyEdgeKind.ITEM_TO_ITEM,
                recipe_id=f"craft_{index}",
                observed_count=1,
                completed_count=1,
                share_milli=1000,
                created_elsewhere_count=0,
                coverage=SupplyCoverage.COMPLETE,
            )
        )
    chains, _truncated = _build_chain_paths(
        edges, policy=default_supply_chain_analysis_policy()
    )
    assert chains
    assert max(chain.depth for chain in chains) <= 8


def test_truncation_sets_partial() -> None:
    graph = build_dependency_graph(
        _evidence(
            [
                _harvest("harvest_grain", "item-grain", tick=0, event_id="evt-1"),
                _harvest("harvest_wood", "item-wood", tick=1, event_id="evt-2"),
            ]
        ),
        policy=SupplyChainAnalysisPolicy(max_edges=1),
    )
    assert "edge_truncated" in graph.notices
    assert graph.coverage is SupplyCoverage.PARTIAL


def test_graph_rows_are_frozen() -> None:
    graph = build_dependency_graph(
        _evidence([_harvest("harvest_grain", "item-grain")]),
        policy=default_supply_chain_analysis_policy(),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        graph.edges[0].observed_count = 99  # type: ignore[misc]
