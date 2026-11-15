# mypy: ignore-errors
"""Hypothesis properties for social-mobility genealogy."""

from __future__ import annotations

from types import SimpleNamespace

from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.social_mobility_contract import (
    build_social_mobility_identity_map,
    social_mobility_owner_token,
)
from analysis.social_mobility_genealogy import (
    harvest_social_mobility_genealogy,
)
from analysis.social_mobility_policy import SocialMobilityAnalysisPolicy
from world.effects import ActionCause
from world.events import (
    AgentCreated,
    KinshipEdgeRecorded,
    OccurrenceContext,
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

_WORLD = WorldId("world-social-mobility-properties")


def _event(details: object, *, tick: int, sequence: int) -> WorldEvent:
    return WorldEvent(
        event_id=EventId(f"evt-{tick}-{sequence}"),
        run_id="run-social-mobility",
        world_id=_WORLD,
        tick=tick,
        sequence=sequence,
        request_id=RequestId(f"req-{tick}-{sequence}"),
        resulting_revision=WorldRevision(tick * 100 + sequence),
        schema_version=22,
        details=details,
        actor_id=EntityId("entity:a"),
        target_id=target_id_for_details(details),
        cause=ActionCause(RequestId(f"req-{tick}-{sequence}"), EntityId("entity:a")),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc:a")),
    )


def _fixture(count: int):
    agents = tuple((f"agent:{index}", f"entity:{index}") for index in range(count + 1))
    created = tuple(
        _event(
            AgentCreated(
                body_id=EntityId(f"entity:{index}"),
                agent_id=f"agent:{index}",
                generation_index=index,
                cohort_id=f"cohort-{index}",
                provenance="demographic_policy",
            ),
            tick=index,
            sequence=0,
        )
        for index in range(1, count + 1)
    )
    edges = tuple(
        _event(
            KinshipEdgeRecorded(
                parent_agent_id=f"agent:{index - 1}",
                child_agent_id=f"agent:{index}",
                established_tick=index,
                edge_id=f"edge-{index}",
            ),
            tick=index,
            sequence=1,
        )
        for index in range(1, count + 1)
    )
    config = SimpleNamespace(
        agents=tuple(
            SimpleNamespace(agent_id=agent_id, entity_id=EntityId(body))
            for agent_id, body in agents
        )
    )
    identity = build_social_mobility_identity_map(
        runner_config=config, events=(*created, *edges)
    )
    return identity, (*created, *edges)


@settings(max_examples=25, deadline=None)
@given(count=st.integers(min_value=1, max_value=5), extra=st.integers(0, 3))
def test_harvest_is_deterministic_and_prefix_stable(count: int, extra: int) -> None:
    identity, events = _fixture(count)
    policy = SocialMobilityAnalysisPolicy(max_lineage_depth=8)
    first = harvest_social_mobility_genealogy(
        events, identity_map=identity, policy=policy
    )
    second = harvest_social_mobility_genealogy(
        events, identity_map=identity, policy=policy
    )
    assert first == second

    if extra:
        extended = events + tuple(
            _event(
                KinshipEdgeRecorded(
                    parent_agent_id="agent:0",
                    child_agent_id=f"agent:{count}",
                    established_tick=count + 1 + index,
                    edge_id=f"repeat-{index}",
                ),
                tick=count + 1 + index,
                sequence=10 + index,
            )
            for index in range(extra)
        )
        grown = harvest_social_mobility_genealogy(
            extended, identity_map=identity, policy=policy
        )
        assert grown.edges[: len(first.edges)] == first.edges


@settings(max_examples=25, deadline=None)
@given(count=st.integers(min_value=1, max_value=5))
def test_tokens_are_only_owner_tokens_and_lags_are_bounded(count: int) -> None:
    identity, events = _fixture(count)
    policy = SocialMobilityAnalysisPolicy()
    harvest = harvest_social_mobility_genealogy(
        events, identity_map=identity, policy=policy
    )
    known = set(identity.reverse)
    for edge in harvest.edges:
        assert edge.parent_token in known
        assert edge.child_token in known
    for entry in harvest.lineages:
        assert entry.ancestor_token in known
        assert entry.descendant_token in known
        assert 1 <= entry.generation_lag <= policy.max_generation_lag
        assert entry.lineage_token.startswith("sml-")
    assert social_mobility_owner_token("entity:0") in known
