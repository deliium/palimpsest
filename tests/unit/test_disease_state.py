# mypy: ignore-errors

"""Private disease row invariants and WorldState channel semantics."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap, _materialize_world
from tests.simulation_helpers import alive_body, make_location, make_weather
from world._disease import (
    DiseaseConditionRow,
    DiseaseInvariantError,
    DiseasePhase,
    bootstrap_disease_rows,
    index_disease_state,
    validate_disease_boundary,
)
from world._state import WorldState, rebuild_world_state
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.values import Health

pytestmark = pytest.mark.unit


def _state(*, disease_state=None, bodies=None) -> WorldState:
    body = alive_body("body-1", location_id="loc-1")
    return WorldState(
        WorldRevision(0),
        locations=(make_location("loc-1"),),
        bodies=(body,) if bodies is None else bodies,
        weather=(make_weather("loc-1"),),
        disease_state=disease_state,
    )


def test_channel_off_versus_enabled_empty() -> None:
    off = _state(disease_state=None)
    assert off.disease_state is None
    on_empty = _state(disease_state={})
    assert on_empty.disease_state is not None
    assert dict(on_empty.disease_state) == {}
    rebuilt = rebuild_world_state(on_empty)
    assert rebuilt.disease_state is not None
    assert dict(rebuilt.disease_state) == {}


def test_rows_are_immutable_and_sorted() -> None:
    body_a = alive_body("body-a", location_id="loc-1")
    body_b = alive_body("body-b", location_id="loc-1")
    rows = {
        body_b.entity_id: DiseaseConditionRow(
            phase=DiseasePhase.LATENT, due_tick=3
        ),
        body_a.entity_id: DiseaseConditionRow(
            phase=DiseasePhase.ACTIVE, due_tick=4, symptomatic=True
        ),
    }
    state = WorldState(
        WorldRevision(0),
        locations=(make_location("loc-1"),),
        bodies=(body_a, body_b),
        weather=(make_weather("loc-1"),),
        disease_state=rows,
    )
    assert list(state.disease_state) == [body_a.entity_id, body_b.entity_id]
    with pytest.raises(TypeError):
        state.disease_state[body_a.entity_id] = DiseaseConditionRow(  # type: ignore[index]
            phase=DiseasePhase.IMMUNE
        )


def test_malformed_phases_and_deadlines() -> None:
    with pytest.raises(DiseaseInvariantError):
        DiseaseConditionRow(phase=DiseasePhase.IMMUNE, due_tick=1)
    with pytest.raises(DiseaseInvariantError):
        DiseaseConditionRow(phase=DiseasePhase.LATENT, due_tick=1, symptomatic=True)
    with pytest.raises(DiseaseInvariantError):
        DiseaseConditionRow(phase=DiseasePhase.ACTIVE, due_tick=1, symptomatic=None)
    body = alive_body("body-1")
    with pytest.raises(DiseaseInvariantError):
        index_disease_state(
            {EntityId("missing"): DiseaseConditionRow(phase=DiseasePhase.IMMUNE)},
            body_index={body.entity_id: body},
            require_living=True,
        )


def test_dead_entity_rejected_at_boundary_not_during_fold() -> None:
    living = alive_body("body-1", location_id="loc-1")
    dead = replace(living, life_status=LifeStatus.DEAD, health=Health(0.0))
    folded = WorldState(
        WorldRevision(1),
        locations=(make_location("loc-1"),),
        bodies=(dead,),
        weather=(make_weather("loc-1"),),
        disease_state={
            dead.entity_id: DiseaseConditionRow(phase=DiseasePhase.LATENT, due_tick=5)
        },
        disease_require_living=False,
    )
    assert folded.disease_state is not None
    with pytest.raises(DiseaseInvariantError, match="disease_dead_entity"):
        validate_disease_boundary(
            folded.disease_state,
            body_index=folded.bodies,
            next_tick=1,
        )


def test_founder_bootstrap_and_due_tick() -> None:
    body = alive_body("body-1", location_id="loc-1")
    rows = bootstrap_disease_rows(
        founder_ids=(body.entity_id,),
        latent_ticks=2,
        tick0=0,
        body_index={body.entity_id: body},
    )
    assert rows[body.entity_id].phase is DiseasePhase.LATENT
    assert rows[body.entity_id].due_tick == 2
    validate_disease_boundary(rows, body_index={body.entity_id: body}, next_tick=2)
    with pytest.raises(DiseaseInvariantError, match="disease_due_overdue"):
        validate_disease_boundary(
            rows, body_index={body.entity_id: body}, next_tick=3
        )


def test_bootstrap_seeds_disease_channel() -> None:
    body = alive_body("body-1", location_id="loc-1")
    rows = bootstrap_disease_rows(
        founder_ids=(),
        latent_ticks=1,
        tick0=0,
        body_index={body.entity_id: body},
    )
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-disease-state"),
        revision=WorldRevision(0),
        locations=(make_location("loc-1"),),
        bodies=(body,),
        weather=(make_weather("loc-1"),),
        registrations=(
            AgentRegistration(agent_id=AgentId("agent-1"), entity_id=body.entity_id),
        ),
        disease_state=rows,
    )
    world = _materialize_world(bootstrap)
    assert world.state.disease_state is not None
    assert dict(world.state.disease_state) == {}
