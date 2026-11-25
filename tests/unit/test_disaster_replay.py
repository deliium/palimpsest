# mypy: ignore-errors

"""DisasterResolved encode/decode, fold, and pair selection contracts."""

from __future__ import annotations

import pytest

from simulation.persistence import checkpoint_schema_for_production
from simulation.serialization import decode_domain, encode_domain
from simulation.versioning import (
    DISASTERS_WRITE_PAIR_CODEC,
    DISASTERS_WRITE_PAIR_EVENT,
    ECOLOGY_WRITE_PAIR_CODEC,
    ECOLOGY_WRITE_PAIR_EVENT,
    OVEREXPLOITATION_WRITE_PAIR_CODEC,
    OVEREXPLOITATION_WRITE_PAIR_EVENT,
)
from tests.simulation_helpers import make_location, make_resource, make_weather
from world._disasters import DisasterState
from world._ecological_resources import bootstrap_ecological_rows
from world._replay import ProjectionError, project_events
from world._state import WorldState
from world.disasters import DisasterKind, DisasterOrigin
from world.effects import SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V25,
    EVENT_SCHEMA_REPLAY_V26,
    EVENT_SCHEMA_REPLAY_V29,
    DisasterOutcome,
    DisasterResolved,
    DisasterResourceTargetView,
    DisasterStockEffectRecord,
    OccurrenceContext,
    WorldEvent,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

pytestmark = pytest.mark.unit

_RES = EntityId("res-food")
_LOC = EntityId("loc-1")
_RUN = "run-1"
_WORLD = WorldId("world-1")
_DIGEST = "a" * 64


def _state(*, quantity: float = 4.0, damage: int = 0) -> WorldState:
    from world.values import ResourceKind

    food = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=quantity,
        maximum_quantity=10.0,
        regeneration_per_tick=1.0,
    )
    rows = bootstrap_ecological_rows(nodes=((food.entity_id, 10),))
    if damage:
        from types import MappingProxyType

        from world._ecological_resources import EcologicalStockRow

        rows = MappingProxyType(
            {
                food.entity_id: EcologicalStockRow(
                    resource_id=food.entity_id,
                    minimum_capacity_tenths=10,
                    damage_tenths=damage,
                )
            }
        )
    return WorldState(
        WorldRevision(0),
        locations=(make_location("loc-1"),),
        resources=(food,),
        weather=(make_weather("loc-1"),),
        ecological_resources=rows,
        ecological_policy_digest=_DIGEST,
        disaster_state=DisasterState(
            policy_sha256=_DIGEST,
            overexploitation_active=False,
            applied_rule_ids=(),
        ),
    )


def _receipt(
    *,
    event_id: str = "evt-disaster-1",
    sequence: int = 0,
    request_id: str = "sys-disaster-1",
    revision: int,
    before: int = 40,
    after: int = 30,
    schema: int = EVENT_SCHEMA_REPLAY_V26,
) -> WorldEvent:
    details = DisasterResolved(
        rule_id="fire-a",
        disaster_kind=DisasterKind.FIRE,
        origin=DisasterOrigin.SCHEDULED,
        target=DisasterResourceTargetView(resource_id=_RES),
        outcome=DisasterOutcome.APPLIED,
        effect=DisasterStockEffectRecord(
            quantity_before_tenths=before,
            quantity_after_tenths=after,
            damage_before_tenths=0,
            damage_after_tenths=0,
        ),
    )
    return WorldEvent(
        event_id=EventId(event_id),
        run_id=_RUN,
        world_id=_WORLD,
        tick=1,
        sequence=sequence,
        request_id=RequestId(request_id),
        resulting_revision=WorldRevision(revision),
        schema_version=schema,
        details=details,
        actor_id=None,
        target_id=_RES,
        cause=SystemCause(
            RequestId(request_id),
            SystemEffectFamily.DISASTER,
            _RES,
            sequence,
        ),
        occurrence=OccurrenceContext(
            origin_location_id=None,
            destination_location_id=None,
            affected_entity_ids=(),
            private_recipient_ids=(),
        ),
    )


def test_disasters_pair_selected_before_overexploitation() -> None:
    schema, codec = checkpoint_schema_for_production(
        production_active=True,
        ecological_feedback_active=True,
        disasters_active=True,
        overexploitation_active=True,
        disease_active=True,
    )
    assert (schema, codec) == (DISASTERS_WRITE_PAIR_EVENT, DISASTERS_WRITE_PAIR_CODEC)
    schema, codec = checkpoint_schema_for_production(
        production_active=True,
        ecological_feedback_active=True,
        overexploitation_active=True,
        disasters_active=False,
    )
    assert (schema, codec) == (
        OVEREXPLOITATION_WRITE_PAIR_EVENT,
        OVEREXPLOITATION_WRITE_PAIR_CODEC,
    )
    schema, codec = checkpoint_schema_for_production(
        production_active=True,
        ecological_feedback_active=True,
        disasters_active=False,
        overexploitation_active=False,
    )
    assert (schema, codec) == (ECOLOGY_WRITE_PAIR_EVENT, ECOLOGY_WRITE_PAIR_CODEC)


def test_encode_decode_disaster_receipt() -> None:
    event = _receipt(revision=1)
    round_tripped = decode_domain(encode_domain(event))
    assert type(round_tripped) is WorldEvent
    assert type(round_tripped.details) is DisasterResolved
    assert round_tripped.details.effect.quantity_after_tenths == 30
    assert round_tripped.schema_version == EVENT_SCHEMA_REPLAY_V26


def test_reject_receipt_on_foreign_schema() -> None:
    with pytest.raises(ValueError):
        _receipt(revision=1, schema=EVENT_SCHEMA_REPLAY_V25)
    with pytest.raises(ValueError):
        _receipt(revision=1, schema=EVENT_SCHEMA_REPLAY_V29)


def test_fold_stock_receipt_marks_applied() -> None:
    state = _state(quantity=4.0)
    event = _receipt(revision=1, before=40, after=30)
    projected = project_events(
        state,
        (event,),
        expected_run_id=_RUN,
        expected_world_id=_WORLD,
    )
    assert projected.resources[_RES].quantity == 3.0
    assert projected.disaster_state.applied_rule_ids == ("fire-a",)
    assert projected.revision == WorldRevision(1)


def test_reject_applied_rule_reuse() -> None:
    state = _state(quantity=4.0)
    state = WorldState(
        state.revision,
        locations=tuple(state.locations.values()),
        resources=tuple(state.resources.values()),
        weather=tuple(state.weather.values()),
        ecological_resources=state.ecological_resources,
        ecological_policy_digest=state.ecological_policy_digest,
        disaster_state=DisasterState(
            policy_sha256=_DIGEST,
            overexploitation_active=False,
            applied_rule_ids=("fire-a",),
        ),
    )
    event = _receipt(revision=1, before=40, after=30)
    with pytest.raises(ProjectionError):
        project_events(
            state,
            (event,),
            expected_run_id=_RUN,
            expected_world_id=_WORLD,
        )
