# mypy: ignore-errors

"""Owner-only symptom cue and private disease occurrence suppression."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from simulation.disease_config import DISEASE_POLICY_ID, DiseaseMechanicsSpec
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.serialization import decode_domain, encode_domain
from tests.physical_helpers import physical_config, two_location_fixture
from tests.simulation_helpers import alive_body, make_location, make_weather
from world._disease import DiseaseConditionRow, DiseasePhase
from world._perception import PerceptionService
from world._state import WorldState, rebuild_world_state
from world.actions import Wait
from world.effects import SystemCause, SystemEffectFamily
from world.events import (
    Died,
    DiseaseRowView,
    DiseaseStateChanged,
    OccurrenceContext,
    WorldEvent,
)
from world.identifiers import EventId, RequestId, WorldId, WorldRevision
from world.models import LifeStatus, non_lethal_physical_rules
from world.observations import ObservationContext

pytestmark = pytest.mark.unit


def _spec(*, founders=(), mortality=0) -> DiseaseMechanicsSpec:
    return DiseaseMechanicsSpec(
        policy_id=DISEASE_POLICY_ID,
        initial_latent_entity_ids=tuple(founders),
        exposure_chance_milli=0,
        transmission_chance_milli=0,
        symptom_chance_milli=1000,
        mortality_chance_milli=mortality,
        latent_ticks=1,
        active_ticks=2,
        immunity_after_recovery=True,
    )


def _context(tick: int = 0) -> ObservationContext:
    return ObservationContext(
        tick=tick,
        physical_rules=non_lethal_physical_rules(),
    )


def test_symptom_cue_owner_only_and_wire_omission() -> None:
    fixture = two_location_fixture()
    owner = fixture.bodies[0]
    peer = fixture.bodies[1]
    rows = {
        owner.entity_id: DiseaseConditionRow(
            phase=DiseasePhase.ACTIVE, due_tick=9, symptomatic=True
        ),
        peer.entity_id: DiseaseConditionRow(
            phase=DiseasePhase.ACTIVE, due_tick=9, symptomatic=False
        ),
    }
    state = WorldState(
        fixture.revision,
        locations=fixture.locations,
        bodies=fixture.bodies,
        items=fixture.items,
        resources=fixture.resources,
        weather=fixture.weather,
        disease_state=rows,
    )
    service = PerceptionService()
    batch = service.project(
        world_id=fixture.world_id,
        state=state,
        observer_ids=(owner.entity_id, peer.entity_id),
        context=_context(),
        prior_events=(),
    )
    by_id = {item.observer_id: item for item in batch}
    assert by_id[owner.entity_id].self_body.symptom_cue == "unwell"
    assert by_id[peer.entity_id].self_body.symptom_cue is None
    owner_doc = json.loads(encode_domain(by_id[owner.entity_id]))
    peer_doc = json.loads(encode_domain(by_id[peer.entity_id]))
    assert owner_doc["data"]["self_body"]["symptom_cue"] == "unwell"
    assert "symptom_cue" not in peer_doc["data"]["self_body"]
    assert (
        decode_domain(encode_domain(by_id[owner.entity_id])).self_body.symptom_cue
        == "unwell"
    )

    latent_only = rebuild_world_state(
        state,
        disease_state={
            owner.entity_id: DiseaseConditionRow(
                phase=DiseasePhase.LATENT, due_tick=3
            )
        },
        replace_disease_state=True,
    )
    latent_obs = service.project(
        world_id=fixture.world_id,
        state=latent_only,
        observer_ids=(owner.entity_id,),
        context=_context(),
        prior_events=(),
    )[0]
    assert latent_obs.self_body.symptom_cue is None

    off = rebuild_world_state(
        state, disease_state=None, replace_disease_state=True
    )
    off_obs = service.project(
        world_id=fixture.world_id,
        state=off,
        observer_ids=(owner.entity_id,),
        context=_context(),
        prior_events=(),
    )[0]
    assert off_obs.self_body.symptom_cue is None
    assert "symptom_cue" not in json.loads(encode_domain(off_obs))["data"][
        "self_body"
    ]


def test_hidden_state_does_not_change_peer_wire_without_cue() -> None:
    fixture = two_location_fixture()
    owner = fixture.bodies[0]
    peer = fixture.bodies[1]
    base = WorldState(
        fixture.revision,
        locations=fixture.locations,
        bodies=fixture.bodies,
        items=fixture.items,
        resources=fixture.resources,
        weather=fixture.weather,
        disease_state={},
    )
    with_hidden = rebuild_world_state(
        base,
        disease_state={
            owner.entity_id: DiseaseConditionRow(phase=DiseasePhase.IMMUNE)
        },
        replace_disease_state=True,
    )
    service = PerceptionService()
    wire_a = encode_domain(
        service.project(
            world_id=fixture.world_id,
            state=base,
            observer_ids=(peer.entity_id,),
            context=_context(),
            prior_events=(),
        )[0]
    )
    wire_b = encode_domain(
        service.project(
            world_id=fixture.world_id,
            state=with_hidden,
            observer_ids=(peer.entity_id,),
            context=_context(),
            prior_events=(),
        )[0]
    )
    assert wire_a == wire_b


def test_disease_transition_not_in_occurrences_and_death_has_no_diagnosis() -> None:
    fixture = two_location_fixture()
    body = fixture.bodies[0]
    active = {
        body.entity_id: DiseaseConditionRow(
            phase=DiseasePhase.ACTIVE, due_tick=0, symptomatic=True
        )
    }
    bootstrap = replace(fixture.as_bootstrap(), disease_state=active)
    engine = WorldEngine(
        config=physical_config(13, rules=non_lethal_physical_rules()),
        bootstrap=bootstrap,
        disease_mechanics=_spec(founders=(body.entity_id,), mortality=1000),
    )
    batch = engine.observe()
    owner_obs = batch.for_observer(body.entity_id)
    assert owner_obs.self_body.symptom_cue == "unwell"
    result = engine.resolve_tick(
        tuple(
            ActionSubmission(batch.token, reg.agent_id, Wait())
            for reg in fixture.registrations
        )
    )
    assert any(type(record.event.details) is Died for record in result.events)
    assert any(
        type(record.event.details) is DiseaseStateChanged for record in result.events
    )
    assert engine._snapshot.world.state.bodies[body.entity_id].life_status is (
        LifeStatus.DEAD
    )
    next_batch = engine.observe()
    for observation in next_batch.observations:
        assert all(
            occurrence.kind != "disease_state_changed"
            for occurrence in observation.occurrences
        )
        for occurrence in observation.occurrences:
            if occurrence.kind == "died":
                assert "death_cause" not in occurrence.public_facts
                assert "disease" not in str(occurrence.public_facts).lower()


def test_internal_event_with_local_context_still_suppressed() -> None:
    body = alive_body("body-1", location_id="loc-1")
    state = WorldState(
        WorldRevision(0),
        locations=(make_location("loc-1"),),
        bodies=(body,),
        weather=(make_weather("loc-1"),),
        disease_state={},
    )
    details = DiseaseStateChanged(
        body_id=body.entity_id,
        before=None,
        after=DiseaseRowView(phase="latent", due_tick=2),
    )
    occurrence = OccurrenceContext(
        origin_location_id=body.location_id,
        destination_location_id=None,
        affected_entity_ids=(body.entity_id,),
        private_recipient_ids=(),
    )
    event = WorldEvent(
        event_id=EventId("evt-disease-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=RequestId("sys-disease-1"),
        resulting_revision=WorldRevision(1),
        schema_version=24,
        details=details,
        actor_id=None,
        target_id=body.entity_id,
        cause=SystemCause(
            RequestId("sys-disease-1"),
            SystemEffectFamily.DISEASE,
            body.entity_id,
            0,
        ),
        occurrence=occurrence,
    )
    observation = PerceptionService().project(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(body.entity_id,),
        context=_context(tick=1),
        prior_events=(event,),
    )[0]
    assert observation.occurrences == ()
