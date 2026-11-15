# mypy: ignore-errors
"""Completed-run bridge for economic-cascade analysis."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from analysis.economic_cascades_contract import CascadeCoverage
from analysis.supply_chain_contract import NONE_TOKEN
from analysis.supply_chain_events import SupplyRecipeSpec, SupplyStageObservation
from experiments.economic_cascades_completed_run import (
    build_completed_run_economic_cascades_analysis,
    cascade_infrastructure_facts,
    cascade_labor_joins,
    cascade_recipe_specs,
    cascade_route_facts,
)
from world.effects import ActionCause, DeathCause
from world.events import (
    Died,
    OccurrenceContext,
    ResourceHarvested,
    ResourceNodeDepleted,
    RouteConditionChanged,
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
from world.production import example_production_catalog
from world.supply_chain import supply_chain_production_catalog

pytestmark = pytest.mark.unit

_WORLD = WorldId("world-cascades-completed")


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


def _runner_result() -> SimpleNamespace:
    catalog = supply_chain_production_catalog(example_production_catalog())
    agent = SimpleNamespace(
        cognition=SimpleNamespace(production_catalog=catalog)
    )
    asset = SimpleNamespace(
        location_id=EntityId("loc-1"),
        kind=SimpleNamespace(value="irrigation"),
        status=SimpleNamespace(value="destroyed"),
    )
    return SimpleNamespace(
        runner_config=SimpleNamespace(agents=(agent,)),
        final_infrastructure_assets=(asset,),
    )


def _route(previous: str, current: str, *, event_id: str) -> WorldEvent:
    return _event(
        RouteConditionChanged(
            origin_location_id=EntityId("loc-a"),
            destination_location_id=EntityId("loc-b"),
            previous_status=previous,
            current_status=current,
            previous_seasonal_availability="open",
            current_seasonal_availability="open",
            duration_ticks=2,
            fatigue_cost=0.5,
            capacity=4,
            risk=0.1,
            infrastructure_quality=0.5,
            blockage_cause="none",
            reason_codes=("test",),
            season=None,
            as_of_tick=0,
        ),
        tick=0,
        sequence=0,
        event_id=event_id,
    )


def _events() -> tuple[WorldEvent, ...]:
    return (
        _event(
            ResourceHarvested(
                RecipeId("harvest_grain"),
                EntityId("res-grain"),
                True,
                2,
                1.0,
                created_item_id=EntityId("item-grain"),
            ),
            tick=0,
            sequence=0,
            event_id="evt-harvest",
        ),
        _event(
            ResourceNodeDepleted(EntityId("res-grain"), 0.0),
            tick=0,
            sequence=1,
            event_id="evt-depleted",
        ),
        _event(
            Died(EntityId("body-1"), DeathCause.COMBINED_NEEDS),
            tick=1,
            sequence=2,
            event_id="evt-died",
        ),
    )


def _stage() -> SupplyStageObservation:
    return SupplyStageObservation(
        tick=0,
        sequence=0,
        window_index=0,
        recipe_id="mill_grain",
        action="craft",
        location_token="loc-1",
        actor_token="body-1",
        item_names=("grain",),
        completed=True,
        attempt=True,
        started_success=True,
        duration_ticks=2,
        created_item_token=NONE_TOKEN,
        cause="craft",
    )


def test_recipe_specs_come_from_the_declared_catalog() -> None:
    specs = cascade_recipe_specs(_runner_result())
    assert specs
    assert "harvest_grain" in {spec.recipe_id for spec in specs}


def test_destroyed_infrastructure_is_retained_as_non_operational() -> None:
    facts = cascade_infrastructure_facts(_runner_result())
    assert facts == (("loc-1", "irrigation", False),)


def test_route_facts_keep_the_latest_status_per_edge() -> None:
    events = (
        _route("open", "closed", event_id="evt-route-1"),
        _route("closed", "restricted", event_id="evt-route-2"),
    )
    assert cascade_route_facts(events) == (
        ("loc-a", "loc-b", "restricted"),
    )


def test_labor_join_uses_the_objective_actor_token() -> None:
    joins = cascade_labor_joins(_events(), [_stage()])
    assert joins == (("body-1", ("mill_grain",)),)


def test_builder_requires_committed_events() -> None:
    with pytest.raises(ValueError):
        build_completed_run_economic_cascades_analysis(
            _runner_result(), committed_events=None, run_id="run-1"
        )


def test_builder_composes_with_explicit_detached_inputs() -> None:
    specs = (
        SupplyRecipeSpec(
            recipe_id="harvest_grain",
            action="harvest",
            resource_input_names=("grain",),
            item_input_names=(),
            input_kinds=(),
            output_name="grain",
            output_kind="food",
        ),
        SupplyRecipeSpec(
            recipe_id="mill_grain",
            action="craft",
            resource_input_names=(),
            item_input_names=("grain",),
            input_kinds=(),
            output_name="flour",
            output_kind="material",
        ),
    )
    analysis = build_completed_run_economic_cascades_analysis(
        _runner_result(),
        committed_events=_events(),
        run_id="run-1",
        recipe_specs=specs,
        stages=[_stage()],
    )
    assert analysis.window_count >= 1
    assert analysis.coverage is not CascadeCoverage.MISSING
