# mypy: ignore-errors

"""Disease schema 24 / codec v22 selection and effect-complete fold."""

from __future__ import annotations

import pytest

from simulation.persistence import checkpoint_schema_for_production
from simulation.versioning import (
    EPIDEMICS_WRITE_PAIR_CODEC,
    EPIDEMICS_WRITE_PAIR_EVENT,
    MEASUREMENT_WRITE_PAIR_CODEC,
    MEASUREMENT_WRITE_PAIR_EVENT,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world._disease import DiseaseConditionRow, DiseasePhase
from world._replay import project_events
from world._state import WorldState
from world.effects import SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V23,
    EVENT_SCHEMA_REPLAY_V24,
    DiseaseRowView,
    DiseaseStateChanged,
    OccurrenceContext,
    WorldEvent,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

pytestmark = pytest.mark.unit


def test_disease_pair_selected_first() -> None:
    schema, codec = checkpoint_schema_for_production(
        production_active=False,
        disease_active=True,
        measurement_active=True,
        travel_network_active=True,
        infrastructure_networks_active=True,
    )
    assert (schema, codec) == (
        EPIDEMICS_WRITE_PAIR_EVENT,
        EPIDEMICS_WRITE_PAIR_CODEC,
    )
    schema, codec = checkpoint_schema_for_production(
        production_active=False,
        measurement_active=True,
    )
    assert (schema, codec) == (
        MEASUREMENT_WRITE_PAIR_EVENT,
        MEASUREMENT_WRITE_PAIR_CODEC,
    )
    schema, codec = checkpoint_schema_for_production(
        production_active=False,
        infrastructure_networks_active=True,
    )
    assert (schema, codec) == (EVENT_SCHEMA_REPLAY_V23, "v21")


def test_fold_disease_state_changed_without_policy() -> None:
    body = alive_body("body-1", location_id="loc-1")
    state = WorldState(
        WorldRevision(0),
        locations=(make_location("loc-1"),),
        bodies=(body,),
        weather=(make_weather("loc-1"),),
        disease_state={
            body.entity_id: DiseaseConditionRow(
                phase=DiseasePhase.LATENT, due_tick=2
            )
        },
    )
    details = DiseaseStateChanged(
        body_id=body.entity_id,
        before=DiseaseRowView(phase="latent", due_tick=2),
        after=DiseaseRowView(phase="active", due_tick=5, symptomatic=True),
    )
    event = WorldEvent(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=2,
        sequence=0,
        request_id=RequestId("sys-1"),
        resulting_revision=WorldRevision(1),
        schema_version=EVENT_SCHEMA_REPLAY_V24,
        details=details,
        actor_id=None,
        target_id=body.entity_id,
        cause=SystemCause(
            RequestId("sys-1"),
            SystemEffectFamily.DISEASE,
            body.entity_id,
            0,
        ),
        occurrence=OccurrenceContext(
            origin_location_id=None,
            destination_location_id=None,
            affected_entity_ids=(),
            private_recipient_ids=(),
        ),
    )
    projected = project_events(
        state,
        (event,),
        expected_run_id="run-1",
        expected_world_id=WorldId("world-1"),
    )
    assert projected.disease_state[body.entity_id].phase is DiseasePhase.ACTIVE
    assert projected.disease_state[body.entity_id].symptomatic is True


def test_reject_disease_event_on_legacy_schema() -> None:
    body_id = EntityId("body-1")
    details = DiseaseStateChanged(
        body_id=body_id,
        before=None,
        after=DiseaseRowView(phase="latent", due_tick=1),
    )
    with pytest.raises(ValueError, match="invalid_event_schema_version"):
        WorldEvent(
            event_id=EventId("evt-legacy"),
            run_id="run-1",
            world_id=WorldId("world-1"),
            tick=0,
            sequence=0,
            request_id=RequestId("sys-legacy"),
            resulting_revision=WorldRevision(1),
            schema_version=EVENT_SCHEMA_REPLAY_V23,
            details=details,
            actor_id=None,
            target_id=body_id,
            cause=SystemCause(
                RequestId("sys-legacy"),
                SystemEffectFamily.DISEASE,
                body_id,
                0,
            ),
            occurrence=OccurrenceContext(
                origin_location_id=None,
                destination_location_id=None,
                affected_entity_ids=(),
                private_recipient_ids=(),
            ),
        )


def test_restore_requires_matching_policy_digest() -> None:
    from dataclasses import replace

    from simulation.disease_checkpoint import (
        DiseaseCheckpointSection,
        policy_sha256_for_spec,
    )
    from simulation.disease_config import DISEASE_POLICY_ID, DiseaseMechanicsSpec
    from simulation.engine import WorldEngine
    from tests.simulation_helpers import hashed_bootstrap_snapshot

    spec = DiseaseMechanicsSpec(
        policy_id=DISEASE_POLICY_ID,
        initial_latent_entity_ids=(),
        exposure_chance_milli=1000,
        transmission_chance_milli=1000,
        symptom_chance_milli=1000,
        mortality_chance_milli=0,
        latent_ticks=1,
        active_ticks=2,
        immunity_after_recovery=True,
    )
    section = DiseaseCheckpointSection(
        rows=(), policy_sha256=policy_sha256_for_spec(spec)
    )
    snapshot = hashed_bootstrap_snapshot(disease_mechanics=section)

    read_only = WorldEngine.restore_from_snapshot(snapshot)
    assert read_only._disease_mechanics is None

    with pytest.raises(ValueError, match="disease_policy_mismatch"):
        WorldEngine.restore_from_snapshot(
            snapshot,
            disease_mechanics=replace(spec, exposure_chance_milli=0),
        )

    bound = WorldEngine.restore_from_snapshot(snapshot, disease_mechanics=spec)
    assert bound._disease_mechanics is spec
