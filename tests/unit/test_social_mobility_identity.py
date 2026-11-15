# mypy: ignore-errors
"""Agent-id ↔ body-token identity translation for social mobility."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from analysis.social_mobility_contract import (
    SocialMobilityError,
    build_social_mobility_identity_map,
    social_mobility_owner_token,
)
from world.events import AgentCreated, AgentEnteredWorld
from world.identifiers import EntityId

pytestmark = pytest.mark.unit


def _config(*pairs: tuple[str, str]) -> SimpleNamespace:
    return SimpleNamespace(
        agents=tuple(
            SimpleNamespace(agent_id=agent_id, entity_id=EntityId(body))
            for agent_id, body in pairs
        )
    )


def _created(agent_id: str, body_id: str, generation: int = 1):
    return SimpleNamespace(
        details=AgentCreated(
            body_id=EntityId(body_id),
            agent_id=agent_id,
            generation_index=generation,
            cohort_id="cohort-1",
            provenance="demographic_policy",
        )
    )


def test_founder_mapping_comes_from_config() -> None:
    identity = build_social_mobility_identity_map(
        runner_config=_config(("agent:alice", "entity:alice")), events=[]
    )
    token = identity.require_token("agent:alice")
    assert token == social_mobility_owner_token("entity:alice")
    assert identity.agent_for_token(token) == "agent:alice"
    assert identity.owner_count == 1


def test_mid_run_mapping_comes_from_committed_events() -> None:
    identity = build_social_mobility_identity_map(
        runner_config=_config(("agent:alice", "entity:alice")),
        events=(
            _created("agent:bob", "entity:bob"),
            SimpleNamespace(
                details=AgentEnteredWorld(
                    body_id=EntityId("entity:carol"),
                    agent_id="agent:carol",
                    location_id=EntityId("loc:home"),
                    entry_tick=1,
                )
            ),
        ),
    )
    assert identity.require_token("agent:bob") == social_mobility_owner_token(
        "entity:bob"
    )
    assert identity.token_for_agent("agent:carol") == social_mobility_owner_token(
        "entity:carol"
    )


def test_agreeing_duplicates_are_a_no_op_and_conflicts_fail() -> None:
    build_social_mobility_identity_map(
        runner_config=_config(("agent:alice", "entity:alice")),
        events=(_created("agent:alice", "entity:alice"),),
    )
    with pytest.raises(SocialMobilityError, match="social_mobility_identity_conflict"):
        build_social_mobility_identity_map(
            runner_config=_config(("agent:alice", "entity:alice")),
            events=(_created("agent:alice", "entity:other"),),
        )


def test_unmapped_owner_is_reported_never_guessed() -> None:
    identity = build_social_mobility_identity_map(
        runner_config=_config(("agent:alice", "entity:alice")), events=[]
    )
    assert identity.token_for_agent("agent:ghost") is None
    with pytest.raises(SocialMobilityError, match="social_mobility_unmapped_owner"):
        identity.require_token("agent:ghost")


def test_round_trip_token_is_stable() -> None:
    identity = build_social_mobility_identity_map(
        runner_config=_config(("agent:alice", "entity:alice")),
        events=(_created("agent:bob", "entity:bob"),),
    )
    token = identity.require_token("agent:bob")
    assert identity.token_for_agent(identity.agent_for_token(token) or "") == token
