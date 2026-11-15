# mypy: ignore-errors
"""Observed outcome harvest across the six social-mobility domains."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from analysis.social_mobility_contract import (
    SocialMobilityDomain,
    SocialMobilityLayer,
    build_social_mobility_identity_map,
    social_mobility_owner_token,
)
from analysis.social_mobility_outcomes import harvest_social_mobility_outcomes
from analysis.social_mobility_policy import SocialMobilityAnalysisPolicy
from world.communications import origin_utterance
from world.effects import ActionCause
from world.events import (
    ItemCrafted,
    OccurrenceContext,
    RepositoryMemberRetrieved,
    Talked,
    WorldEvent,
    target_id_for_details,
)
from world.identifiers import (
    AgentId,
    EntityId,
    EventId,
    RecipeId,
    RequestId,
    WorldId,
    WorldRevision,
)

pytestmark = pytest.mark.unit

_WORLD = WorldId("world-social-mobility-outcomes")


def _event(
    details: object,
    *,
    tick: int,
    sequence: int = 0,
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


def _crafted(item: str, recipe: str, *, tick: int, holder: str = "entity:a"):
    return _event(
        ItemCrafted(
            recipe_id=RecipeId(recipe),
            created_item_id=EntityId(item),
            resulting_holder_id=EntityId(holder),
            duration_ticks=1,
        ),
        tick=tick,
        sequence=1,
        actor=holder,
    )


def _identity(*pairs: tuple[str, str]):
    return build_social_mobility_identity_map(
        runner_config=SimpleNamespace(
            agents=tuple(
                SimpleNamespace(agent_id=agent_id, entity_id=EntityId(body))
                for agent_id, body in pairs
            )
        ),
        events=(),
    )


def _token(body: str) -> str:
    return social_mobility_owner_token(body)


def _domain_rows(harvest, domain: SocialMobilityDomain):
    return [row for row in harvest.rows if row.domain is domain]


def test_resources_exclude_tools_and_assets_add_tools() -> None:
    harvest = harvest_social_mobility_outcomes(
        (
            _crafted("item-tool", "craft_tool", tick=0),
            _crafted("item-food", "craft_food", tick=1),
        ),
        identity_map=_identity(("agent:a", "entity:a")),
        recipe_output_kinds={"craft_tool": "tool", "craft_food": "food"},
    )
    resources = _domain_rows(harvest, SocialMobilityDomain.RESOURCES)
    assets = _domain_rows(harvest, SocialMobilityDomain.PRODUCTIVE_ASSETS)
    assert resources[-1].quantity == 1
    assert assets[-1].quantity == 1
    assert resources[-1].layer is SocialMobilityLayer.OBJECTIVE_OUTCOME
    assert assets[-1].layer is SocialMobilityLayer.OBJECTIVE_OUTCOME


def test_skills_come_from_owner_scoped_audits_in_token_space() -> None:
    identity = _identity(("agent:a", "entity:a"))
    audit = SimpleNamespace(
        owner_id=AgentId("agent:a"),
        active=True,
        content_key="technique:fire",
        acquired_tick=1,
    )
    harvest = harvest_social_mobility_outcomes(
        (), identity_map=identity, practical_knowledge_audits=(audit,)
    )
    rows = _domain_rows(harvest, SocialMobilityDomain.SKILLS)
    assert rows[0].owner_token == _token("entity:a")
    assert rows[0].quantity == 1
    assert rows[0].layer is SocialMobilityLayer.OWNER_OUTCOME


def test_skills_count_distinct_active_content_keys() -> None:
    identity = _identity(("agent:a", "entity:a"))
    audits = (
        SimpleNamespace(
            owner_id=AgentId("agent:a"),
            active=True,
            content_key="technique:fire",
            acquired_tick=0,
        ),
        SimpleNamespace(
            owner_id=AgentId("agent:a"),
            active=True,
            content_key="technique:fire",
            acquired_tick=1,
        ),
        SimpleNamespace(
            owner_id=AgentId("agent:a"),
            active=True,
            content_key="technique:wheel",
            acquired_tick=1,
        ),
    )
    harvest = harvest_social_mobility_outcomes(
        (),
        identity_map=identity,
        practical_knowledge_audits=audits,
        policy=SocialMobilityAnalysisPolicy(window_ticks=1),
    )
    rows = _domain_rows(harvest, SocialMobilityDomain.SKILLS)
    assert [(row.window_index, row.quantity) for row in rows] == [(0, 1), (1, 2)]


def test_education_counts_teaching_and_repository_receipts() -> None:
    identity = _identity(("agent:a", "entity:a"))
    teaching = SimpleNamespace(
        agent_id=AgentId("agent:a"), tick=1, store=SimpleNamespace(value="advice")
    )
    repository = _event(
        RepositoryMemberRetrieved(
            repository_id=EntityId("repo:1"),
            artifact_id=EntityId("artifact:1"),
            member_count=1,
            actor_id=EntityId("entity:a"),
            hold=True,
        ),
        tick=2,
        sequence=2,
    )
    harvest = harvest_social_mobility_outcomes(
        (repository,), identity_map=identity, teaching_audits=(teaching,)
    )
    rows = _domain_rows(harvest, SocialMobilityDomain.EDUCATIONAL_ACCESS)
    assert sum(row.quantity for row in rows) >= 2


def test_influence_counts_distinct_inbound_partners() -> None:
    utterance = origin_utterance(
        text="it is cold",
        speaker_id=EntityId("entity:b"),
    )
    identity = _identity(("agent:a", "entity:a"), ("agent:b", "entity:b"))
    events = (
        _event(
            Talked(recipient_id=EntityId("entity:a"), utterance=utterance),
            tick=1,
            sequence=1,
            actor="entity:b",
        ),
        _event(
            Talked(recipient_id=EntityId("entity:a"), utterance=utterance),
            tick=2,
            sequence=2,
            actor="entity:b",
        ),
    )
    harvest = harvest_social_mobility_outcomes(events, identity_map=identity)
    rows = _domain_rows(harvest, SocialMobilityDomain.SOCIAL_INFLUENCE)
    assert len(rows) == 1
    assert rows[0].owner_token == _token("entity:a")
    assert rows[0].quantity == 1


def test_organization_roles_count_distinct_offices() -> None:
    identity = _identity(("agent:a", "entity:a"))
    ledger = SimpleNamespace(
        assignments=(
            SimpleNamespace(
                occupant_id="agent:a", office_id="office:1", stance="held", last_tick=1
            ),
            SimpleNamespace(
                occupant_id="agent:a", office_id="office:1", stance="held", last_tick=2
            ),
            SimpleNamespace(
                occupant_id="agent:a", office_id="office:2", stance="held", last_tick=3
            ),
            SimpleNamespace(
                occupant_id="agent:a",
                office_id="office:3",
                stance="rejected",
                last_tick=4,
            ),
        )
    )
    harvest = harvest_social_mobility_outcomes(
        (), identity_map=identity, organization_operation_rows=(ledger,)
    )
    rows = _domain_rows(harvest, SocialMobilityDomain.ORGANIZATION_ROLES)
    assert rows[-1].quantity == 2
    assert rows[-1].layer is SocialMobilityLayer.OWNER_OUTCOME


def test_unmapped_owner_rows_are_skipped_and_reported() -> None:
    audit = SimpleNamespace(
        owner_id=AgentId("agent:ghost"),
        active=True,
        content_key="technique:fire",
        acquired_tick=1,
    )
    harvest = harvest_social_mobility_outcomes(
        (),
        identity_map=_identity(("agent:a", "entity:a")),
        practical_knowledge_audits=(audit,),
    )
    assert all(row.owner_token != "agent:ghost" for row in harvest.rows)
    assert "social_mobility_unmapped_owner" in harvest.notices


def test_missing_sources_stay_unavailable_never_zero() -> None:
    harvest = harvest_social_mobility_outcomes(
        (), identity_map=_identity(("agent:a", "entity:a"))
    )
    assert harvest.rows == ()
    assert "social_mobility_domain_unavailable" in harvest.notices
