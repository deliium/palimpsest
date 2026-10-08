"""Engine resolution of Experiment commands and replay-v15 write pair."""

from __future__ import annotations

import pytest

from simulation.persistence import checkpoint_schema_for_production
from simulation.serialization import decode_domain, encode_domain
from tests.simulation_helpers import (
    make_item,
    make_location,
    make_resource,
    weather_for_locations,
)
from world._experiment_laws import ExperimentLaw, ExperimentLawCatalog
from world._operations import (
    OperationAccepted,
    validate_action_request,
)
from world._replay import project_events
from world._rules import RuleDisposition, apply_operation
from world._state import WorldState
from world.actions import ActionRequest, Experiment
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V14,
    EVENT_SCHEMA_REPLAY_V15,
    ExperimentResolved,
    OccurrenceContext,
    make_physical_replayable_event,
)
from world.experimentation import (
    ExperimentDeltaKind,
    ExperimentHarmBand,
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)
from world.identifiers import (
    EntityId,
    EventId,
    ProposalId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.models import (
    AgentBody,
    LifeStatus,
    default_physical_rules,
)
from world.production import example_production_catalog
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

pytestmark = pytest.mark.unit

_WORLD = WorldId("world-1")
_ACTOR = EntityId("body-1")


def _body() -> AgentBody:
    return AgentBody(
        entity_id=_ACTOR,
        location_id=EntityId("loc-1"),
        health=Health(50),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _state(*, item_kind: str = "material") -> WorldState:
    from world.values import ItemKind, ResourceKind

    locations = (make_location("loc-1"),)
    return WorldState(
        WorldRevision(1),
        locations=locations,
        bodies=(_body(),),
        items=(
            make_item(
                "item-1",
                name="wood",
                kind=ItemKind(item_kind),
                location_id="loc-1",
            ),
        ),
        resources=(
            make_resource(
                "res-1",
                name="stone",
                kind=ResourceKind.MATERIAL,
                location_id="loc-1",
            ),
        ),
        weather=weather_for_locations(locations),
    )


def _law(**overrides: object) -> ExperimentLaw:
    payload: dict[str, object] = {
        "operator": ExperimentOperator.COMBINE,
        "operand_a_kind": "item:material",
        "operand_b_kind": "resource:material",
        "process_token": ExperimentProcessToken.NONE,
        "outcome_class": ExperimentOutcomeClass.SUCCESS,
        "delta": ExperimentDeltaKind.EMIT_CATALOG_PRODUCT,
        "product_id": "harvest_wood",
        "harm_band": ExperimentHarmBand.NONE,
    }
    payload.update(overrides)
    return ExperimentLaw(**payload)  # type: ignore[arg-type]


def _catalog(*laws: ExperimentLaw) -> ExperimentLawCatalog:
    return ExperimentLawCatalog(laws or (_law(),), example_production_catalog())


def _apply(
    state: WorldState,
    *,
    catalog: ExperimentLawCatalog | None,
    hypothesis_id: str = "h1",
    operand_a: str = "item-1",
    operand_b: str | None = "res-1",
    operator: ExperimentOperator = ExperimentOperator.COMBINE,
    process: ExperimentProcessToken = ExperimentProcessToken.NONE,
):
    command = Experiment(
        operator=operator,
        operand_a_id=EntityId(operand_a),
        operand_b_id=None if operand_b is None else EntityId(operand_b),
        process_token=process,
        hypothesis_id=hypothesis_id,
    )
    request = ActionRequest(
        request_id=RequestId("req-1"),
        proposal_id=ProposalId("prop-1"),
        world_id=_WORLD,
        actor_id=_ACTOR,
        revision=state.revision,
        command=command,
    )
    admitted = validate_action_request(
        world_id=_WORLD, state=state, request=request
    )
    assert type(admitted) is OperationAccepted
    return apply_operation(
        state,
        admitted.operation,
        rules=default_physical_rules(),
        tick=0,
        experiment_catalog=catalog,
    )


def _details(application: object) -> ExperimentResolved:
    details = application.event_details  # type: ignore[attr-defined]
    assert type(details) is ExperimentResolved
    return details


def test_success_emits_catalog_product() -> None:
    state = _state()
    applied = _apply(state, catalog=_catalog())
    details = _details(applied)
    assert details.outcome_class == "success"
    assert details.delta == "emit_catalog_product"
    assert details.discovery_mode == "deliberate"
    assert details.created_item_id is not None
    assert details.created_item_id in applied.next_state.items
    assert details.created_item_id in applied.next_state.bodies[_ACTOR].inventory


def test_partial_emit_records_partial_delta() -> None:
    applied = _apply(
        _state(),
        catalog=_catalog(
            _law(
                outcome_class=ExperimentOutcomeClass.PARTIAL_SUCCESS,
                delta=ExperimentDeltaKind.PARTIAL_EMIT,
            )
        ),
    )
    details = _details(applied)
    assert details.outcome_class == "partial_success"
    assert details.delta == "partial_emit"
    assert details.created_item_id in applied.next_state.items


def test_unlisted_pair_is_failure_without_product() -> None:
    applied = _apply(
        _state(),
        catalog=_catalog(
            _law(
                operand_a_kind="item:food",
                operand_b_kind="item:food",
                delta=ExperimentDeltaKind.NONE,
                outcome_class=ExperimentOutcomeClass.FAILURE,
                product_id="",
            )
        ),
    )
    details = _details(applied)
    assert details.outcome_class == "failure"
    assert details.delta == "none"
    assert len(applied.next_state.items) == 1


def test_harm_bands_use_physical_scalars() -> None:
    rules = default_physical_rules()
    minor = _apply(
        _state(),
        catalog=_catalog(
            _law(
                outcome_class=ExperimentOutcomeClass.HARM,
                delta=ExperimentDeltaKind.APPLY_HARM_BAND,
                product_id="",
                harm_band=ExperimentHarmBand.MINOR,
            )
        ),
    )
    assert _details(minor).outcome_class == "harm"
    assert minor.next_state.bodies[_ACTOR].health.value == pytest.approx(
        50.0 - rules.hunger_damage
    )
    serious = _apply(
        _state(),
        catalog=_catalog(
            _law(
                outcome_class=ExperimentOutcomeClass.HARM,
                delta=ExperimentDeltaKind.APPLY_HARM_BAND,
                product_id="",
                harm_band=ExperimentHarmBand.SERIOUS,
            )
        ),
    )
    assert serious.next_state.bodies[_ACTOR].health.value == pytest.approx(
        50.0 - float(rules.attack_damage_min)
    )


def test_unexpected_consumes_operand() -> None:
    applied = _apply(
        _state(),
        catalog=_catalog(
            _law(
                outcome_class=ExperimentOutcomeClass.UNEXPECTED,
                delta=ExperimentDeltaKind.CONSUME_OPERAND,
                product_id="",
            )
        ),
        hypothesis_id="",
    )
    details = _details(applied)
    assert details.outcome_class == "unexpected"
    assert details.delta == "consume_operand"
    assert details.discovery_mode == "accidental"
    assert EntityId("item-1") not in applied.next_state.items


def test_missing_operand_is_failure() -> None:
    applied = _apply(_state(), catalog=_catalog(), operand_a="missing-item")
    details = _details(applied)
    assert details.outcome_class == "failure"
    assert details.delta == "none"
    assert applied.result.disposition is RuleDisposition.EVENT_ONLY


def test_prefix_mismatch_is_failure() -> None:
    applied = _apply(
        _state(),
        catalog=_catalog(),
        operand_a="res-1",
        operand_b="item-1",
    )
    details = _details(applied)
    assert details.outcome_class == "failure"
    assert details.delta == "none"


def test_channel_off_rejects_without_event() -> None:
    applied = _apply(_state(), catalog=None)
    assert applied.result.disposition is RuleDisposition.REJECT
    assert applied.result.reason.value == "experiment_channel_off"
    assert applied.event_details is None


def test_replay_matches_applied_delta() -> None:
    state = _state()
    catalog = _catalog()
    applied = _apply(state, catalog=catalog)
    details = _details(applied)
    event = make_physical_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=_WORLD,
        tick=0,
        sequence=0,
        cause=ActionCause(request_id=RequestId("req-1"), actor_id=_ACTOR),
        resulting_revision=WorldRevision(2),
        details=details,
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=EVENT_SCHEMA_REPLAY_V15,
    )
    projected = project_events(
        state,
        (event,),
        expected_run_id="run-1",
        expected_world_id=_WORLD,
        production_catalog=example_production_catalog(),
    )
    assert set(projected.items) == set(applied.next_state.items)
    assert (
        projected.bodies[_ACTOR].inventory
        == applied.next_state.bodies[_ACTOR].inventory
    )


def test_experiment_event_requires_schema_15() -> None:
    details = ExperimentResolved(
        operator="combine",
        operand_a_id=EntityId("item-1"),
        process_token="none",
        outcome_class="failure",
        delta="none",
        discovery_mode="deliberate",
    )
    with pytest.raises(ValueError):
        make_physical_replayable_event(
            event_id=EventId("evt-1"),
            run_id="run-1",
            world_id=_WORLD,
            tick=0,
            sequence=0,
            cause=ActionCause(request_id=RequestId("req-1"), actor_id=_ACTOR),
            resulting_revision=WorldRevision(1),
            details=details,
            occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
            schema_version=EVENT_SCHEMA_REPLAY_V14,
        )


def test_command_and_event_round_trip() -> None:
    command = Experiment(
        operator=ExperimentOperator.VARY_PROCESS,
        operand_a_id=EntityId("item-1"),
        process_token=ExperimentProcessToken.HARVEST,
        hypothesis_id="",
    )
    decoded = decode_domain(encode_domain(command))
    assert decoded == command
    details = ExperimentResolved(
        operator="vary_process",
        operand_a_id=EntityId("item-1"),
        process_token="harvest",
        outcome_class="failure",
        delta="none",
        discovery_mode="accidental",
    )
    event = make_physical_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=_WORLD,
        tick=0,
        sequence=0,
        cause=ActionCause(request_id=RequestId("req-1"), actor_id=_ACTOR),
        resulting_revision=WorldRevision(1),
        details=details,
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=EVENT_SCHEMA_REPLAY_V15,
    )
    restored = decode_domain(encode_domain(event))
    assert restored.details == event.details
    assert restored.schema_version == EVENT_SCHEMA_REPLAY_V15


def test_write_pair_only_when_channel_active() -> None:
    active = checkpoint_schema_for_production(
        production_active=True,
        knowledge_repositories_active=True,
        durable_records_active=True,
        bounded_experimentation_active=True,
    )
    assert active == (EVENT_SCHEMA_REPLAY_V15, "v12")
    idle = checkpoint_schema_for_production(
        production_active=True,
        knowledge_repositories_active=True,
        durable_records_active=True,
        bounded_experimentation_active=False,
    )
    assert idle == (EVENT_SCHEMA_REPLAY_V14, "v11")
