# mypy: ignore-errors
"""Completed-run social-mobility bridge and collector injection."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from analysis.social_mobility_contract import (
    SocialMobilityDomain,
    social_mobility_owner_token,
)
from experiments.collectors import assemble_arm_metric_bundle
from experiments.social_mobility_completed_run import (
    build_completed_run_social_mobility_analysis,
    social_mobility_recipe_mappings,
)
from world.effects import ActionCause
from world.events import (
    AgentCreated,
    ItemCrafted,
    KinshipEdgeRecorded,
    OccurrenceContext,
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

_WORLD = WorldId("world-social-mobility-completed-run")


def _event(details: object, *, tick: int, sequence: int = 0, actor: str = "entity:a"):
    return WorldEvent(
        event_id=EventId(f"evt-{tick}-{sequence}"),
        run_id="run:social-mobility",
        world_id=_WORLD,
        tick=tick,
        sequence=sequence,
        request_id=RequestId(f"req-{tick}-{sequence}"),
        resulting_revision=WorldRevision(tick * 10 + sequence),
        schema_version=22,
        details=details,
        actor_id=EntityId(actor),
        target_id=target_id_for_details(details),
        cause=ActionCause(RequestId(f"req-{tick}-{sequence}"), EntityId(actor)),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc:a")),
    )


def _config():
    return SimpleNamespace(
        agents=(
            SimpleNamespace(
                agent_id=AgentId("agent:a"),
                entity_id=EntityId("entity:a"),
                cognition=SimpleNamespace(production_catalog=None),
            ),
            SimpleNamespace(
                agent_id=AgentId("agent:b"),
                entity_id=EntityId("entity:b"),
                cognition=SimpleNamespace(production_catalog=None),
            ),
        )
    )


def _events():
    return (
        _event(
            AgentCreated(
                body_id=EntityId("entity:b"),
                agent_id="agent:b",
                generation_index=1,
                cohort_id="cohort-1",
                provenance="demographic_policy",
            ),
            tick=1,
        ),
        _event(
            KinshipEdgeRecorded(
                parent_agent_id="agent:a",
                child_agent_id="agent:b",
                established_tick=1,
                edge_id="edge-1",
            ),
            tick=1,
            sequence=1,
        ),
        _event(
            ItemCrafted(
                recipe_id=RecipeId("craft_tool"),
                created_item_id=EntityId("item-tool"),
                resulting_holder_id=EntityId("entity:a"),
                duration_ticks=1,
            ),
            tick=2,
            sequence=2,
        ),
        _event(
            ItemCrafted(
                recipe_id=RecipeId("craft_tool"),
                created_item_id=EntityId("item-tool-child"),
                resulting_holder_id=EntityId("entity:b"),
                duration_ticks=1,
            ),
            tick=2,
            sequence=3,
            actor="entity:b",
        ),
    )


def test_recipe_mappings_are_empty_without_a_catalog() -> None:
    assert social_mobility_recipe_mappings(_config()) == ({}, {})


def test_completed_run_builder_rejects_empty_or_unordered_events() -> None:
    with pytest.raises(Exception, match="social_mobility_invalid_input"):
        build_completed_run_social_mobility_analysis(
            SimpleNamespace(),
            runner_config=_config(),
            committed_events=(),
            run_id="run:social-mobility",
        )


def test_completed_run_builder_joins_founder_and_child_tokens() -> None:
    result = SimpleNamespace(
        practical_knowledge_audits=(),
        teaching_audits=(),
        organization_operation_ledgers=(),
    )
    analysis = build_completed_run_social_mobility_analysis(
        result,
        runner_config=_config(),
        committed_events=_events(),
        run_id="run:social-mobility",
        window_end=31,
    )
    assert analysis.genealogy_edge_count == 1
    assert analysis.resolved_pair_count >= 1
    resource_rows = [
        row
        for row in analysis.domain_rows
        if row.domain is SocialMobilityDomain.RESOURCES
    ]
    assert resource_rows
    assert analysis.coverage_row is not None
    assert social_mobility_owner_token("entity:a") != social_mobility_owner_token(
        "entity:b"
    )


def _arm(events, *, kinship: bool = True, outcome_channel: bool = True):
    if not kinship:
        events = tuple(
            event for event in events if type(event.details) is not KinshipEdgeRecorded
        )
    runner_config = SimpleNamespace(
        agents=_config().agents,
        v4_capability_flags=SimpleNamespace(
            organizations=False,
            markets_credit=False,
            infrastructure_networks=False,
            supply_chains=False,
        ),
        durable_records=object() if outcome_channel else None,
        structured_commitments=None,
        subjective_valuation=None,
    )
    runner_result = SimpleNamespace(
        ticks_committed=2,
        committed_events=events,
        practical_knowledge_audits=(),
        teaching_audits=(),
        organization_operation_ledgers=(),
    )
    return SimpleNamespace(
        assignment=SimpleNamespace(
            run_id=SimpleNamespace(value="run:social-mobility"),
            runner_config=runner_config,
        ),
        runner_result=runner_result,
        config_fingerprint="a" * 40,
        committed_events=events,
    )


def test_collector_injects_analysis_only_with_kinship_and_outcome_channel() -> None:
    bundle = assemble_arm_metric_bundle(_arm(_events()))
    families = {document.metric_family for document in bundle.documents}
    assert "resource_mobility" in families
    assert "social_mobility_coverage" in families


def test_collector_stays_disabled_without_kinship_or_outcome_channel() -> None:
    for arm in (
        _arm(_events(), kinship=False),
        _arm(_events(), outcome_channel=False),
    ):
        bundle = assemble_arm_metric_bundle(arm)
        families = {document.metric_family for document in bundle.documents}
        assert "resource_mobility" not in families


def test_collector_failure_is_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "experiments.social_mobility_completed_run."
        "build_completed_run_social_mobility_analysis",
        _boom,
    )
    bundle = assemble_arm_metric_bundle(_arm(_events()))
    families = {document.metric_family for document in bundle.documents}
    assert "resource_mobility" not in families
