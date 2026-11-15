# mypy: ignore-errors
"""Committed-event disruption harvest for the five economic-cascade classes."""

from __future__ import annotations

import pytest

from analysis.economic_cascades_contract import (
    CascadeCoverage,
    CascadeDisruptionKind,
    EconomicCascadesError,
)
from analysis.economic_cascades_events import (
    CascadeDisruptionResult,
    harvest_economic_cascade_disruptions,
)
from analysis.economic_cascades_policy import policy_with
from world.effects import ActionCause, DeathCause
from world.events import (
    Died,
    EventDetails,
    InfrastructureDestroyed,
    OccurrenceContext,
    ResourceHarvested,
    ResourceNodeDepleted,
    ResourceNodeRecovered,
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

pytestmark = pytest.mark.unit

_WORLD = WorldId("world-cascades-events")


def _event(
    details: EventDetails,
    *,
    tick: int = 0,
    sequence: int = 0,
    event_id: str = "evt-1",
    actor: str | None = "body-1",
) -> WorldEvent:
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
        actor_id=None if actor is None else EntityId(actor),
        target_id=target_id_for_details(details),
        cause=ActionCause(RequestId(f"req-{event_id}"), EntityId(actor or "body-1")),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
    )


def _harvest(
    *,
    recipe: str = "harvest_grain",
    node: str = "res-grain",
    tick: int = 0,
    sequence: int = 0,
    event_id: str = "evt-harvest",
) -> WorldEvent:
    return _event(
        ResourceHarvested(
            RecipeId(recipe),
            EntityId(node),
            True,
            2,
            1.0,
            created_item_id=EntityId("item-1"),
        ),
        tick=tick,
        sequence=sequence,
        event_id=event_id,
    )


def _depleted(
    *,
    node: str = "res-grain",
    tick: int = 0,
    sequence: int = 0,
    event_id: str = "evt-depleted",
) -> WorldEvent:
    return _event(
        ResourceNodeDepleted(EntityId(node), 0.0),
        tick=tick,
        sequence=sequence,
        event_id=event_id,
    )


def _route(
    *,
    previous: str,
    current: str,
    tick: int = 0,
    sequence: int = 0,
    event_id: str = "evt-route",
) -> WorldEvent:
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
            as_of_tick=tick,
        ),
        tick=tick,
        sequence=sequence,
        event_id=event_id,
    )


def _destroyed(
    *,
    tick: int = 0,
    sequence: int = 0,
    event_id: str = "evt-destroyed",
) -> WorldEvent:
    return _event(
        InfrastructureDestroyed(
            asset_id=EntityId("infra-1"),
            asset_kind="well",
            topology="node",
            status="destroyed",
            integrity=0.0,
            location_id=EntityId("loc-1"),
            endpoint_location_id=None,
            linked_structure_id=None,
            linked_project_id=EntityId("project-1"),
            tick=tick,
        ),
        tick=tick,
        sequence=sequence,
        event_id=event_id,
    )


def _died(
    *,
    tick: int = 0,
    sequence: int = 0,
    event_id: str = "evt-died",
) -> WorldEvent:
    return _event(
        Died(EntityId("body-7"), DeathCause.COMBINED_NEEDS),
        tick=tick,
        sequence=sequence,
        event_id=event_id,
        actor="body-7",
    )


def test_five_classes_are_declared_but_four_are_event_backed() -> None:
    events = [
        _harvest(tick=0, sequence=0),
        _depleted(tick=0, sequence=1),
        _route(previous="open", current="closed", tick=1, sequence=2),
        _destroyed(tick=1, sequence=3),
        _died(tick=2, sequence=4),
    ]
    result = harvest_economic_cascade_disruptions(events)
    kinds = [row.kind for row in result.rows]
    assert kinds == [
        CascadeDisruptionKind.INFRASTRUCTURE_DESTRUCTION,
        CascadeDisruptionKind.POPULATION_LOSS,
        CascadeDisruptionKind.RESOURCE_LOSS,
        CascadeDisruptionKind.ROUTE_CLOSURE,
    ]
    assert CascadeDisruptionKind.TOOL_SHORTAGE not in kinds
    assert result.coverage is CascadeCoverage.COMPLETE
    assert result.event_count == 5
    assert dict(result.kind_counts) == {
        "infrastructure_destruction": 1,
        "population_loss": 1,
        "resource_loss": 1,
        "route_closure": 1,
    }


def test_resource_depletion_uses_the_preceding_harvest_recipe() -> None:
    result = harvest_economic_cascade_disruptions(
        [_harvest(tick=0, sequence=0), _depleted(tick=0, sequence=1)]
    )
    assert len(result.rows) == 1
    assert result.rows[0].subject_token == "harvest_grain"
    assert result.rows[0].kind is CascadeDisruptionKind.RESOURCE_LOSS


def test_depletion_without_harvest_uses_a_resource_subject() -> None:
    result = harvest_economic_cascade_disruptions(
        [_depleted(node="res-unknown", tick=0, sequence=1)]
    )
    assert result.rows[0].subject_token == "resource:res-unknown"


def test_depletion_crossing_is_emitted_once() -> None:
    events = [
        _harvest(tick=0, sequence=0),
        _depleted(tick=0, sequence=1),
        _depleted(node="res-grain", tick=1, sequence=2, event_id="evt-depleted-2"),
    ]
    result = harvest_economic_cascade_disruptions(events)
    assert (
        len(
            [
                row
                for row in result.rows
                if row.kind is CascadeDisruptionKind.RESOURCE_LOSS
            ]
        )
        == 1
    )


def test_recovery_allows_a_later_crossing() -> None:
    events = [
        _harvest(tick=0, sequence=0),
        _depleted(tick=0, sequence=1),
        _event(
            ResourceNodeRecovered(EntityId("res-grain"), 5.0),
            tick=1,
            sequence=2,
            event_id="evt-recovered",
        ),
        _depleted(tick=2, sequence=3, event_id="evt-depleted-2"),
    ]
    result = harvest_economic_cascade_disruptions(events)
    assert (
        len(
            [
                row
                for row in result.rows
                if row.kind is CascadeDisruptionKind.RESOURCE_LOSS
            ]
        )
        == 2
    )


def test_repeated_closed_route_is_not_duplicated() -> None:
    events = [
        _route(previous="open", current="closed", tick=0, sequence=0),
        _route(
            previous="closed",
            current="restricted",
            tick=1,
            sequence=1,
            event_id="evt-route-2",
        ),
    ]
    result = harvest_economic_cascade_disruptions(events)
    assert len(result.rows) == 1
    assert result.rows[0].subject_token == "route:loc-a->loc-b"


def test_route_reopening_then_closing_emits_a_new_row() -> None:
    events = [
        _route(previous="open", current="closed", tick=0, sequence=0),
        _route(
            previous="closed",
            current="open",
            tick=1,
            sequence=1,
            event_id="evt-route-2",
        ),
        _route(
            previous="open",
            current="closed",
            tick=2,
            sequence=2,
            event_id="evt-route-3",
        ),
    ]
    result = harvest_economic_cascade_disruptions(events)
    assert len(result.rows) == 2


def test_population_loss_uses_the_objective_body_token() -> None:
    result = harvest_economic_cascade_disruptions([_died()])
    assert result.rows[0].subject_token == "body-7"


def test_event_cap_truncates_deterministically() -> None:
    policy = policy_with(max_events=2)
    events = [
        _died(tick=0, sequence=0),
        _destroyed(tick=1, sequence=1),
        _died(tick=2, sequence=2, event_id="evt-died-2"),
    ]
    result = harvest_economic_cascade_disruptions(events, policy=policy)
    assert result.coverage is CascadeCoverage.PARTIAL
    assert "events_truncated" in result.notices
    assert result.event_count == 2


def test_disruption_cap_truncates_deterministically() -> None:
    policy = policy_with(max_disruptions=1)
    events = [_died(tick=0, sequence=0), _destroyed(tick=1, sequence=1)]
    result = harvest_economic_cascade_disruptions(events, policy=policy)
    assert result.coverage is CascadeCoverage.PARTIAL
    assert "disruptions_truncated" in result.notices
    assert len(result.rows) == 1


def test_empty_input_is_missing_coverage() -> None:
    result = harvest_economic_cascade_disruptions([])
    assert result.rows == ()
    assert result.coverage is CascadeCoverage.MISSING
    assert result.event_count == 0


def test_out_of_order_duplicate_sequence_is_rejected() -> None:
    events = [_died(tick=1, sequence=0), _destroyed(tick=1, sequence=0)]
    with pytest.raises(EconomicCascadesError):
        harvest_economic_cascade_disruptions(events)


def test_non_event_input_is_rejected() -> None:
    with pytest.raises(EconomicCascadesError):
        harvest_economic_cascade_disruptions([object()])


def test_result_dataclass_validates_containers() -> None:
    assert CascadeDisruptionResult().coverage is CascadeCoverage.MISSING
