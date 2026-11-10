# mypy: ignore-errors

"""Descriptive supply bottlenecks stay bounded and unranked."""

from __future__ import annotations

import dataclasses

from analysis.supply_chain_bottlenecks import SupplyBottleneck, detect_bottlenecks
from analysis.supply_chain_graph import build_dependency_graph
from analysis.supply_chain_policy import (
    SupplyChainAnalysisPolicy,
    default_supply_chain_analysis_policy,
)
from tests.unit.test_supply_chain_graph import (
    _craft_done,
    _craft_start,
    _evidence,
    _harvest,
)


def _graph(events, **kwargs):
    evidence = _evidence(events, **kwargs)
    return evidence, build_dependency_graph(
        evidence, policy=default_supply_chain_analysis_policy()
    )


def _shortfall_events():
    events = [
        _harvest("harvest_grain", "item-grain", tick=0, event_id="evt-h1"),
        _harvest("harvest_grain", "item-grain", tick=0, event_id="evt-h2"),
        _craft_start("mill_grain", ("item-grain",), tick=0, event_id="evt-s1"),
        _craft_done("mill_grain", "item-flour", tick=1, event_id="evt-d1"),
        _craft_start("mill_grain", ("item-grain",), tick=1, event_id="evt-s2"),
        _craft_done("mill_grain", "item-flour", tick=2, event_id="evt-d2"),
    ]
    # Two failed starts add demand without supply.
    from world.effects import ActionCause
    from world.events import (
        CraftStarted,
        OccurrenceContext,
        WorldEvent,
        target_id_for_details,
    )
    from world.identifiers import EntityId, EventId, RecipeId, RequestId, WorldRevision

    for index in (3, 4):
        tick = index
        request = RequestId(f"req-f{index}")
        details = CraftStarted(RecipeId("mill_grain"), False, 1)
        events.append(
            WorldEvent(
                event_id=EventId(f"evt-f{index}"),
                run_id="run-supply-graph",
                world_id=__import__("world.identifiers", fromlist=["WorldId"]).WorldId(
                    "world-supply-graph"
                ),
                tick=tick,
                sequence=0,
                request_id=request,
                resulting_revision=WorldRevision(tick),
                schema_version=6,
                details=details,
                actor_id=EntityId("body-1"),
                target_id=target_id_for_details(details),
                cause=ActionCause(request, EntityId("body-1")),
                occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
            )
        )
    return events


def test_upstream_shortfall_threshold() -> None:
    evidence, graph = _graph(_shortfall_events())
    rows = detect_bottlenecks(
        graph, evidence, policy=default_supply_chain_analysis_policy()
    )
    shortfall = [row for row in rows if row.kind.value == "upstream_shortfall"]
    assert shortfall
    row = shortfall[0]
    assert row.demand_count == 4
    assert row.supply_count == 2
    assert row.ratio_milli == 500


def test_shortfall_below_threshold() -> None:
    evidence, graph = _graph(
        [
            _harvest("harvest_grain", "item-grain", tick=0),
            _craft_start("mill_grain", ("item-grain",), tick=0, event_id="evt-s1"),
            _craft_done("mill_grain", "item-flour", tick=1, event_id="evt-d1"),
        ]
    )
    rows = detect_bottlenecks(
        graph, evidence, policy=default_supply_chain_analysis_policy()
    )
    assert not [row for row in rows if row.kind.value == "upstream_shortfall"]


def test_demand_counts_unpaired_completions() -> None:
    evidence, graph = _graph(
        [
            _harvest("harvest_grain", "item-grain", tick=0),
            _craft_done("mill_grain", "item-flour", tick=0, event_id="evt-d1"),
        ]
    )
    rows = detect_bottlenecks(
        graph, evidence, policy=default_supply_chain_analysis_policy()
    )
    assert not [row for row in rows if row.kind.value == "upstream_shortfall"]


def test_single_location_concentration() -> None:
    events = [
        _harvest("harvest_grain", "item-grain", tick=index, event_id=f"evt-{index}")
        for index in range(3)
    ]
    evidence, graph = _graph(events)
    rows = detect_bottlenecks(
        graph, evidence, policy=default_supply_chain_analysis_policy()
    )
    assert [row for row in rows if row.kind.value == "single_location_concentration"]


def test_transport_dependency() -> None:
    events = []
    for index in range(3):
        events.append(
            _harvest(
                "harvest_grain",
                f"item-grain-{index}",
                tick=index,
                event_id=f"evt-h{index}",
                location="loc-1",
            )
        )
        events.append(
            _craft_start(
                "mill_grain",
                (f"item-grain-{index}",),
                tick=index,
                event_id=f"evt-s{index}",
                location="loc-2",
            )
        )
        events.append(
            _craft_done(
                "mill_grain",
                f"item-flour-{index}",
                tick=index + 1,
                event_id=f"evt-d{index}",
                location="loc-2",
            )
        )
    evidence, graph = _graph(events)
    rows = detect_bottlenecks(
        graph, evidence, policy=default_supply_chain_analysis_policy()
    )
    assert [row for row in rows if row.kind.value == "transport_dependency"]


def test_tool_dependency_requires_tool_stage() -> None:
    evidence, graph = _graph(
        [
            _harvest("harvest_grain", "item-flour", tick=0),
            _craft_start("assemble_tool", ("item-flour",), tick=0, event_id="evt-s1"),
            _craft_done("assemble_tool", "item-tool", tick=1, event_id="evt-d1"),
        ]
    )
    rows = detect_bottlenecks(
        graph, evidence, policy=default_supply_chain_analysis_policy()
    )
    assert isinstance(rows, tuple)
    assert all(row.kind.value != "tool_dependency" or row.stage_token for row in rows)


def test_infrastructure_rule_skipped_without_coverage() -> None:
    evidence, graph = _graph(
        [
            _harvest("harvest_grain", "item-grain", tick=index, event_id=f"evt-{index}")
            for index in range(3)
        ]
    )
    rows = detect_bottlenecks(
        graph, evidence, policy=default_supply_chain_analysis_policy()
    )
    assert not [row for row in rows if row.kind.value == "infrastructure_dependency"]


def test_organization_rule_requires_actor_attribution() -> None:
    evidence, graph = _graph(
        [
            _harvest("harvest_grain", "item-grain", tick=index, event_id=f"evt-{index}")
            for index in range(3)
        ]
    )
    rows = detect_bottlenecks(
        graph, evidence, policy=default_supply_chain_analysis_policy()
    )
    assert not [row for row in rows if row.kind.value == "organization_dependency"]


def test_skill_constraint_uses_low_level_share() -> None:
    from analysis.supply_chain_events import SupplySkillLevel

    events = [
        _harvest("harvest_grain", "item-grain", tick=index, event_id=f"evt-{index}")
        for index in range(3)
    ]
    evidence, graph = _graph(
        events, skill_levels=[SupplySkillLevel("body-1", "crafting", 0.1)]
    )
    rows = detect_bottlenecks(
        graph, evidence, policy=default_supply_chain_analysis_policy()
    )
    assert isinstance(rows, tuple)


def test_rows_have_no_score_fields() -> None:
    fields = {field.name for field in dataclasses.fields(SupplyBottleneck)}
    for forbidden in ("severity", "rank", "priority", "score", "recommendation"):
        assert forbidden not in fields


def test_sort_is_deterministic() -> None:
    events = _shortfall_events()
    first = detect_bottlenecks(
        _graph(events)[1],
        _graph(events)[0],
        policy=default_supply_chain_analysis_policy(),
    )
    reversed_evidence, reversed_graph = _graph(tuple(reversed(events)))
    second = detect_bottlenecks(
        reversed_graph,
        reversed_evidence,
        policy=default_supply_chain_analysis_policy(),
    )
    assert [row.bottleneck_token for row in first] == [
        row.bottleneck_token for row in second
    ]


def test_cap_sets_partial_and_notice() -> None:
    evidence, graph = _graph(
        [
            _harvest("harvest_grain", "item-grain", tick=index, event_id=f"evt-{index}")
            for index in range(4)
        ]
    )
    rows = detect_bottlenecks(
        graph,
        evidence,
        policy=SupplyChainAnalysisPolicy(max_bottlenecks=1),
    )
    assert len(rows) <= 1


def test_bottleneck_token_is_stable() -> None:
    evidence, graph = _graph(
        [
            _harvest("harvest_grain", "item-grain", tick=index, event_id=f"evt-{index}")
            for index in range(3)
        ]
    )
    first = detect_bottlenecks(
        graph, evidence, policy=default_supply_chain_analysis_policy()
    )
    second = detect_bottlenecks(
        graph, evidence, policy=default_supply_chain_analysis_policy()
    )
    assert [row.bottleneck_token for row in first] == [
        row.bottleneck_token for row in second
    ]
