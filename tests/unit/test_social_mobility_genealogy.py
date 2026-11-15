# mypy: ignore-errors
"""Committed-event genealogy and generation harvest."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.models import AgentId
from analysis.social_mobility_contract import (
    SocialMobilityCoverage,
    build_social_mobility_identity_map,
    social_mobility_owner_token,
)
from analysis.social_mobility_genealogy import (
    harvest_social_mobility_genealogy,
)
from analysis.social_mobility_policy import SocialMobilityAnalysisPolicy
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.demographic_policy import DemographicEntryCandidate
from simulation.engine import WorldEngine
from simulation.models import SimulationRunConfig
from simulation.runner_models import (
    example_population_lifecycle_spec,
    seed_bootstrap_lifecycle_records,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.effects import ActionCause
from world.events import (
    AgentCreated,
    KinshipEdgeRecorded,
    OccurrenceContext,
    Searched,
    WorldEvent,
    target_id_for_details,
)
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.lifecycle import OriginProvenance

pytestmark = pytest.mark.unit

_WORLD = WorldId("world-social-mobility")


def _event(
    details: object,
    *,
    tick: int,
    sequence: int,
    actor: str | None = "entity:a",
) -> WorldEvent:
    return WorldEvent(
        event_id=EventId(f"evt-{tick}-{sequence}"),
        run_id="run-social-mobility",
        world_id=_WORLD,
        tick=tick,
        sequence=sequence,
        request_id=RequestId(f"req-{tick}-{sequence}"),
        resulting_revision=WorldRevision(tick * 10 + sequence),
        schema_version=22,
        details=details,
        actor_id=None if actor is None else EntityId(actor),
        target_id=target_id_for_details(details),
        cause=ActionCause(
            RequestId(f"req-{tick}-{sequence}"), EntityId(actor or "entity:a")
        ),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc:a")),
    )


def _created(agent_id: str, body: str, generation: int, *, tick: int):
    return _event(
        AgentCreated(
            body_id=EntityId(body),
            agent_id=agent_id,
            generation_index=generation,
            cohort_id=f"cohort-{generation}",
            provenance="demographic_policy",
        ),
        tick=tick,
        sequence=0,
    )


def _edge(parent: str, child: str, *, tick: int, sequence: int = 1):
    return _event(
        KinshipEdgeRecorded(
            parent_agent_id=parent,
            child_agent_id=child,
            established_tick=tick,
            edge_id=f"edge-{parent}-{child}",
        ),
        tick=tick,
        sequence=sequence,
    )


def _config(*pairs: tuple[str, str]):
    return SimpleNamespace(
        agents=tuple(
            SimpleNamespace(agent_id=agent_id, entity_id=EntityId(body))
            for agent_id, body in pairs
        )
    )


def _identity(*pairs: tuple[str, str], events=()):
    return build_social_mobility_identity_map(
        runner_config=_config(*pairs), events=events
    )


def test_empty_events_return_missing_without_raising() -> None:
    harvest = harvest_social_mobility_genealogy(
        (), identity_map=_identity(("agent:a", "entity:a"))
    )
    assert harvest.coverage is SocialMobilityCoverage.MISSING
    assert harvest.edges == ()


def test_bootstrap_generation_zero_and_mid_run_child() -> None:
    identity = _identity(
        ("agent:a", "entity:a"),
        ("agent:b", "entity:b"),
        events=(_created("agent:b", "entity:b", 1, tick=1),),
    )
    harvest = harvest_social_mobility_genealogy(
        (
            _created("agent:b", "entity:b", 1, tick=1),
            _edge("agent:a", "agent:b", tick=1),
        ),
        identity_map=identity,
    )
    assert harvest.owner_count == 2
    assert dict(harvest.generations) == {
        social_mobility_owner_token("entity:a"): 0,
        social_mobility_owner_token("entity:b"): 1,
    }
    assert len(harvest.edges) == 1
    edge = harvest.edges[0]
    assert (edge.parent_generation, edge.child_generation) == (0, 1)
    assert harvest.lineages[0].generation_lag == 1
    assert harvest.coverage is SocialMobilityCoverage.COMPLETE


def test_three_generation_chain_yields_lag_one_two_and_three() -> None:
    created = (
        _created("agent:b", "entity:b", 1, tick=1),
        _created("agent:c", "entity:c", 2, tick=2),
        _created("agent:d", "entity:d", 3, tick=3),
    )
    identity = _identity(
        ("agent:a", "entity:a"),
        ("agent:b", "entity:b"),
        ("agent:c", "entity:c"),
        ("agent:d", "entity:d"),
        events=created,
    )
    edges = (
        _edge("agent:a", "agent:b", tick=1),
        _edge("agent:b", "agent:c", tick=2),
        _edge("agent:c", "agent:d", tick=3),
    )
    harvest = harvest_social_mobility_genealogy(
        (*created, *edges), identity_map=identity
    )
    lags = {entry.generation_lag for entry in harvest.lineages}
    assert lags == {1, 2, 3}
    b = social_mobility_owner_token("entity:b")
    d = social_mobility_owner_token("entity:d")
    assert any(
        entry.ancestor_token == b
        and entry.descendant_token == d
        and entry.generation_lag == 2
        for entry in harvest.lineages
    )


def test_duplicate_edge_keeps_earliest_tick() -> None:
    identity = _identity(
        ("agent:a", "entity:a"),
        ("agent:b", "entity:b"),
        events=(_created("agent:b", "entity:b", 1, tick=1),),
    )
    events = (
        _created("agent:b", "entity:b", 1, tick=1),
        _edge("agent:a", "agent:b", tick=5, sequence=2),
        _edge("agent:a", "agent:b", tick=3, sequence=3),
    )
    harvest = harvest_social_mobility_genealogy(events, identity_map=identity)
    assert len(harvest.edges) == 1
    assert harvest.edges[0].established_tick == 3


def test_unmapped_parent_is_reported_and_dropped() -> None:
    identity = _identity(
        ("agent:b", "entity:b"),
        events=(_created("agent:b", "entity:b", 1, tick=1),),
    )
    harvest = harvest_social_mobility_genealogy(
        (
            _created("agent:b", "entity:b", 1, tick=1),
            _edge("agent:ghost", "agent:b", tick=1),
        ),
        identity_map=identity,
    )
    assert harvest.edges == ()
    assert "social_mobility_unmapped_owner" in harvest.notices
    assert harvest.coverage is SocialMobilityCoverage.PARTIAL


def test_out_of_range_generation_is_reported() -> None:
    identity = _identity(
        ("agent:a", "entity:a"),
        ("agent:b", "entity:b"),
        events=(_created("agent:b", "entity:b", 40, tick=1),),
    )
    harvest = harvest_social_mobility_genealogy(
        (
            _created("agent:b", "entity:b", 40, tick=1),
            _edge("agent:a", "agent:b", tick=1),
        ),
        identity_map=identity,
    )
    assert "social_mobility_generation_out_of_range" in harvest.notices
    assert harvest.coverage is SocialMobilityCoverage.PARTIAL
    assert social_mobility_owner_token("entity:b") not in dict(harvest.generations)
    assert harvest.edges == ()


def test_non_agent_event_targets_are_not_counted_as_owners() -> None:
    identity = _identity(
        ("agent:a", "entity:a"),
        ("agent:b", "entity:b"),
    )
    searched = _event(
        Searched(
            target_id=EntityId("item:wood"),
            success=True,
            created_item_id=EntityId("item:new"),
            extracted_quantity=1.0,
            resulting_resource_quantity=1.0,
        ),
        tick=1,
        sequence=2,
    )
    harvest = harvest_social_mobility_genealogy(
        (searched,), identity_map=identity
    )
    assert harvest.owner_count == 2
    assert social_mobility_owner_token("item:wood") not in dict(harvest.generations)


def test_owner_and_event_caps_truncate_deterministically() -> None:
    identity = _identity(
        ("agent:a", "entity:a"),
        ("agent:b", "entity:b"),
        events=(_created("agent:b", "entity:b", 1, tick=1),),
    )
    policy = SocialMobilityAnalysisPolicy(max_owners=1, max_event_rows=1)
    harvest = harvest_social_mobility_genealogy(
        (
            _created("agent:b", "entity:b", 1, tick=1),
            _edge("agent:a", "agent:b", tick=1),
        ),
        identity_map=identity,
        policy=policy,
    )
    assert harvest.owner_count == 1
    assert "social_mobility_owners_truncated" in harvest.notices
    assert "social_mobility_events_truncated" in harvest.notices
    assert harvest.coverage is SocialMobilityCoverage.PARTIAL


def test_real_population_admission_events_map_generations() -> None:
    body = alive_body("body-1")
    bootstrap = WorldBootstrap(
        world_id=_WORLD,
        revision=WorldRevision(0),
        locations=(make_location(body_capacity=4),),
        bodies=(body,),
        weather=(make_weather(),),
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
    )
    spec = example_population_lifecycle_spec(max_population=4)
    engine = WorldEngine(
        config=SimulationRunConfig(seed=3),
        bootstrap=bootstrap,
        population_lifecycle=spec,
        lifecycle_records=seed_bootstrap_lifecycle_records(
            registrations=bootstrap.registrations, spec=spec
        ),
    )
    admission = engine.admit_population_entry(
        DemographicEntryCandidate(
            agent_id=AgentId("entrant-1"),
            body_id=EntityId("body-entrant-1"),
            spawn_location_id=EntityId("loc-1"),
            generation_index=1,
            cohort_id="cohort-1",
            provenance=OriginProvenance.DEMOGRAPHIC_POLICY,
            name_prefix="entrant",
            sort_key=("entrant-1", "body-entrant-1"),
        )
    )
    events = engine.export_events().events
    harvest = harvest_social_mobility_genealogy(
        events,
        identity_map=_identity(("agent-1", "body-1"), events=events),
    )
    assert dict(harvest.generations)[
        social_mobility_owner_token(admission.body_id.value)
    ] == 1
    assert harvest.owner_count == 2


def test_rows_are_token_only() -> None:
    identity = _identity(
        ("agent:a", "entity:a"),
        ("agent:b", "entity:b"),
        events=(_created("agent:b", "entity:b", 1, tick=1),),
    )
    harvest = harvest_social_mobility_genealogy(
        (
            _created("agent:b", "entity:b", 1, tick=1),
            _edge("agent:a", "agent:b", tick=1),
        ),
        identity_map=identity,
    )
    rendered = repr(harvest)
    assert "agent:a" not in rendered
    assert "entity:a" not in rendered
    assert "smo-" in rendered
