# mypy: ignore-errors
"""Independent caps for the composed economic-cascade analysis."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.economic_cascades_analysis import harvest_economic_cascades_analysis
from analysis.economic_cascades_contract import CascadeCoverage
from analysis.economic_cascades_detection import detect_economic_cascade_episodes
from analysis.economic_cascades_policy import policy_with
from analysis.economic_cascades_rows import CascadeStageRow
from analysis.supply_chain_contract import NONE_TOKEN
from analysis.supply_chain_events import SupplyRecipeSpec, SupplyStageObservation
from world.effects import ActionCause
from world.events import (
    OccurrenceContext,
    ResourceHarvested,
    ResourceNodeDepleted,
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

_WORLD = WorldId("world-cascades-bounds")


def _event(details, *, tick: int, sequence: int, event_id: str) -> WorldEvent:
    return WorldEvent(
        event_id=EventId(event_id),
        run_id="run-cascades",
        world_id=_WORLD,
        tick=tick,
        sequence=sequence,
        request_id=RequestId(f"req-{event_id}"),
        resulting_revision=WorldRevision(tick),
        schema_version=27,
        details=details,
        actor_id=EntityId("body-1"),
        target_id=target_id_for_details(details),
        cause=ActionCause(RequestId(f"req-{event_id}"), EntityId("body-1")),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
    )


def _events() -> tuple[WorldEvent, ...]:
    return (
        _event(
            ResourceHarvested(
                RecipeId("harvest_ore"),
                EntityId("res-ore"),
                True,
                2,
                1.0,
                created_item_id=EntityId("item-ore"),
            ),
            tick=0,
            sequence=0,
            event_id="evt-harvest",
        ),
        _event(
            ResourceNodeDepleted(EntityId("res-ore"), 0.0),
            tick=0,
            sequence=1,
            event_id="evt-depleted",
        ),
    )


def _recipes() -> tuple[SupplyRecipeSpec, ...]:
    return (
        SupplyRecipeSpec(
            recipe_id="harvest_ore",
            action="harvest",
            resource_input_names=("ore",),
            item_input_names=(),
            input_kinds=(),
            output_name="ore",
            output_kind="material",
        ),
        SupplyRecipeSpec(
            recipe_id="smelt_ore",
            action="craft",
            resource_input_names=(),
            item_input_names=("ore",),
            input_kinds=(),
            output_name="metal",
            output_kind="material",
        ),
        SupplyRecipeSpec(
            recipe_id="forge_ore",
            action="craft",
            resource_input_names=(),
            item_input_names=("ore",),
            input_kinds=(),
            output_name="ingot",
            output_kind="material",
        ),
    )


def _stage(
    *,
    completed: bool,
    sequence: int = 0,
    recipe: str = "smelt_ore",
    location: str = "loc-1",
) -> SupplyStageObservation:
    return SupplyStageObservation(
        tick=0,
        sequence=sequence,
        window_index=0,
        recipe_id=recipe,
        action="craft",
        location_token=location,
        actor_token="body-1",
        item_names=("ore",),
        completed=completed,
        attempt=True,
        started_success=True,
        duration_ticks=2,
        created_item_token=NONE_TOKEN,
        cause="craft",
    )


def test_chain_cap_is_independent() -> None:
    analysis = harvest_economic_cascades_analysis(
        events=_events(),
        recipe_specs=_recipes(),
        stages=[
            _stage(completed=False),
            _stage(completed=False, sequence=1, recipe="forge_ore"),
        ],
        policy=policy_with(max_chains=1),
    )
    assert analysis.chain_count <= 1
    assert analysis.coverage is CascadeCoverage.PARTIAL


def test_stage_cap_is_independent() -> None:
    analysis = harvest_economic_cascades_analysis(
        events=_events(),
        recipe_specs=_recipes(),
        stages=[
            _stage(completed=True, sequence=index, location=f"loc-{index}")
            for index in range(4)
        ],
        policy=policy_with(max_stages=2),
    )
    assert analysis.stage_count <= 2
    assert "stages_truncated" in analysis.notices


def test_notice_cap_is_enforced() -> None:
    analysis = harvest_economic_cascades_analysis(
        events=_events(),
        recipe_specs=_recipes(),
        stages=[],
        policy=policy_with(max_notices=1),
    )
    assert len(analysis.notices) <= 1


def test_coverage_is_missing_only_without_rows() -> None:
    analysis = harvest_economic_cascades_analysis(
        events=_events(),
        recipe_specs=_recipes(),
        stages=[_stage(completed=True)],
    )
    assert analysis.coverage is not CascadeCoverage.MISSING
    assert analysis.row_count >= 1


@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=1, max_value=8))
def test_chain_count_never_exceeds_cap(cap: int) -> None:
    analysis = harvest_economic_cascades_analysis(
        events=_events(),
        recipe_specs=_recipes(),
        stages=[_stage(completed=True), _stage(completed=False, sequence=1)],
        policy=policy_with(max_chains=cap),
    )
    assert analysis.chain_count <= cap
    assert analysis.max_depth <= 6


@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=1, max_value=8))
def test_notice_count_never_exceeds_cap(cap: int) -> None:
    analysis = harvest_economic_cascades_analysis(
        events=_events(),
        recipe_specs=_recipes(),
        stages=[],
        policy=policy_with(max_notices=cap),
    )
    assert len(analysis.notices) <= cap


@settings(max_examples=50, deadline=None)
@given(
    st.integers(min_value=1, max_value=64),
    st.integers(min_value=0, max_value=64),
)
def test_every_shortfall_share_is_bounded(demand: int, completions: int) -> None:
    row = CascadeStageRow(
        window_index=0,
        window_tick=0,
        recipe_id="mill_grain",
        action="craft",
        output_name="flour",
        output_kind="material",
        location_token="loc-1",
        demand_count=demand,
        attempt_count=demand,
        completion_count=min(completions, demand),
        tool_dependent=False,
        has_infrastructure=False,
        coverage=CascadeCoverage.COMPLETE,
    )
    detection = detect_economic_cascade_episodes(disruptions=[], stages=[row])
    assert 0 <= detection.stage_rows[0].shortfall_share_milli <= 1000
