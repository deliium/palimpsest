# mypy: ignore-errors
"""Collapse-recovery evidence projection and capture wrapper qualification."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from analysis.collapse_recovery_evidence import (
    CollapseBatch,
    CollapseReceiptKind,
    CollapseSourceCoverage,
    OwnerLaneState,
)
from experiments.catalog import base_runner_config_from_scenario
from experiments.collapse_recovery_capture import (
    frame_from_resilience_boundary,
    project_collapse_batch_events,
    run_with_collapse_recovery_capture,
)
from simulation.models import RunId
from simulation.resilience_evidence import ResilienceBoundaryFacts
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    RunnerStopPolicy,
    WorldScenarioSpec,
)
from tests.simulation_helpers import (
    alive_body,
    make_location,
    make_weather,
)
from world.communications import origin_utterance
from world.effects import ActionCause, DeathCause, SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V29,
    Asked,
    Attacked,
    Died,
    ExchangeCompleted,
    Fed,
    Helped,
    ItemCrafted,
    JourneyArrived,
    OccurrenceContext,
    ResourceHarvested,
    Talked,
    Told,
    WorldEvent,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import (
    EntityId,
    EventId,
    RecipeId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.models import default_physical_rules
from world.values import WeatherCondition

pytestmark = pytest.mark.unit

_RUN = "run-collapse"
_WORLD = WorldId("world-collapse")


def _utterance(*, speaker: str = "body-a"):
    return origin_utterance(
        text="ping",
        speaker_id=EntityId(speaker),
        concepts=("c1",),
        relations=(),
        sender_confidence=0.5,
    )


def _event(
    *,
    event_id: str,
    sequence: int,
    details: object,
    actor_id: EntityId | None = None,
    occurrence: OccurrenceContext | None = None,
    origin_location_id: EntityId | None = None,
    tick: int = 0,
    revision: int = 1,
) -> WorldEvent:
    if origin_location_id is None:
        origin_location_id = EntityId("loc-a")
    request_id = RequestId(f"req-{event_id}")
    if actor_id is None:
        cause: ActionCause | SystemCause = SystemCause(
            request_id,
            SystemEffectFamily.TRAVEL,
            EntityId("system-1"),
            sequence,
        )
    else:
        cause = ActionCause(request_id, actor_id)
    if occurrence is None:
        occurrence = build_occurrence_context(
            details,  # type: ignore[arg-type]
            origin_location_id=origin_location_id,
        )
    return make_physical_replayable_event(
        event_id=EventId(event_id),
        run_id=_RUN,
        world_id=_WORLD,
        tick=tick,
        sequence=sequence,
        cause=cause,
        resulting_revision=WorldRevision(revision),
        details=details,  # type: ignore[arg-type]
        occurrence=occurrence,
        schema_version=EVENT_SCHEMA_REPLAY_V29,
    )


def _registered() -> dict[str, str]:
    return {
        "body-a": "agent-a",
        "body-b": "agent-b",
        "body-c": "agent-c",
    }


def _regions() -> dict[str, str]:
    return {
        "loc-a": "region-north",
        "loc-b": "region-south",
        "loc-c": "region-north",
    }


def test_empty_tick_projects_empty_batch() -> None:
    batch = project_collapse_batch_events(
        (),
        tick=0,
        resulting_revision=1,
        registered_bodies=_registered(),
        location_regions=_regions(),
    )
    assert batch.raw_event_count == 0
    assert batch.receipts == ()


def test_multi_item_exchange_counts_once() -> None:
    details = ExchangeCompleted(
        actor_id=EntityId("body-a"),
        counterparty_id=EntityId("body-b"),
        act="accept",
        give_item_ids=(EntityId("item-1"), EntityId("item-2")),
        take_item_ids=(EntityId("item-3"),),
        give_item_kinds=("food", "material"),
        take_item_kinds=("tool",),
    )
    event = _event(
        event_id="ex-1",
        sequence=1,
        details=details,
        actor_id=EntityId("body-a"),
        origin_location_id=EntityId("loc-a"),
    )
    batch = project_collapse_batch_events(
        (event,),
        tick=0,
        resulting_revision=1,
        registered_bodies=_registered(),
        location_regions=_regions(),
    )
    exchanges = [
        row for row in batch.receipts if row.kind is CollapseReceiptKind.EXCHANGE
    ]
    contacts = [
        row
        for row in batch.receipts
        if row.kind is CollapseReceiptKind.EXCHANGE_CONTACT
    ]
    assert len(exchanges) == 1
    assert len(contacts) == 1
    assert exchanges[0].site_region_id == "region-north"


def test_failed_harvest_and_craft_excluded() -> None:
    failed_harvest = _event(
        event_id="h-fail",
        sequence=1,
        details=ResourceHarvested(
            recipe_id=RecipeId("harvest_wood"),
            resource_id=EntityId("res-1"),
            success=False,
            duration_ticks=1,
            resulting_resource_quantity=1.0,
            created_item_id=None,
        ),
        actor_id=EntityId("body-a"),
        origin_location_id=EntityId("loc-a"),
    )
    ok_harvest = _event(
        event_id="h-ok",
        sequence=2,
        details=ResourceHarvested(
            recipe_id=RecipeId("harvest_wood"),
            resource_id=EntityId("res-1"),
            success=True,
            duration_ticks=1,
            resulting_resource_quantity=0.5,
            created_item_id=EntityId("item-h"),
        ),
        actor_id=EntityId("body-a"),
        origin_location_id=EntityId("loc-a"),
    )
    craft = _event(
        event_id="c-ok",
        sequence=3,
        details=ItemCrafted(
            recipe_id=RecipeId("craft_tool"),
            created_item_id=EntityId("item-c"),
            resulting_holder_id=EntityId("body-a"),
            duration_ticks=1,
            success=True,
        ),
        actor_id=EntityId("body-a"),
        origin_location_id=EntityId("loc-a"),
    )
    batch = project_collapse_batch_events(
        (failed_harvest, ok_harvest, craft),
        tick=0,
        resulting_revision=1,
        registered_bodies=_registered(),
        location_regions=_regions(),
    )
    kinds = [row.kind for row in batch.receipts]
    assert kinds == [CollapseReceiptKind.HARVEST, CollapseReceiptKind.CRAFT]


def test_delivered_vs_undelivered_speech() -> None:
    utterance = _utterance()
    delivered = _event(
        event_id="talk-ok",
        sequence=1,
        details=Talked(recipient_id=EntityId("body-b"), utterance=utterance),
        actor_id=EntityId("body-a"),
    )
    undelivered = _event(
        event_id="talk-miss",
        sequence=2,
        details=Asked(recipient_id=EntityId("body-b"), utterance=utterance),
        actor_id=EntityId("body-a"),
        occurrence=OccurrenceContext(
            origin_location_id=EntityId("loc-a"),
            private_recipient_ids=(),
        ),
    )
    told = _event(
        event_id="tell-ok",
        sequence=3,
        details=Told(recipient_id=EntityId("body-b"), utterance=utterance),
        actor_id=EntityId("body-a"),
    )
    batch = project_collapse_batch_events(
        (delivered, undelivered, told),
        tick=0,
        resulting_revision=1,
        registered_bodies=_registered(),
        location_regions=_regions(),
    )
    assert [row.event_id for row in batch.receipts] == ["talk-ok", "tell-ok"]


def test_journey_per_participant_excludes_equal_region() -> None:
    cross = _event(
        event_id="j-cross",
        sequence=1,
        details=JourneyArrived(
            journey_id="journey-1",
            participant_body_ids=(EntityId("body-a"), EntityId("body-b")),
            origin_location_id=EntityId("loc-a"),
            destination_location_id=EntityId("loc-b"),
        ),
        origin_location_id=None,
    )
    same = _event(
        event_id="j-same",
        sequence=2,
        details=JourneyArrived(
            journey_id="journey-2",
            participant_body_ids=(EntityId("body-c"),),
            origin_location_id=EntityId("loc-a"),
            destination_location_id=EntityId("loc-c"),
        ),
        origin_location_id=None,
    )
    batch = project_collapse_batch_events(
        (cross, same),
        tick=0,
        resulting_revision=1,
        registered_bodies=_registered(),
        location_regions=_regions(),
    )
    arrivals = [
        row for row in batch.receipts if row.kind is CollapseReceiptKind.JOURNEY_ARRIVAL
    ]
    assert len(arrivals) == 2
    assert {row.participant_body_id for row in arrivals} == {"body-a", "body-b"}
    assert arrivals[0].origin_location_id == "loc-a"
    assert arrivals[0].destination_location_id == "loc-b"


def test_conflicting_destination_leaves_site_unassigned() -> None:
    event = _event(
        event_id="atk-1",
        sequence=1,
        details=Attacked(
            target_id=EntityId("body-b"),
            hit=True,
            damage=1,
            resulting_target_health=0.8,
        ),
        actor_id=EntityId("body-a"),
        occurrence=OccurrenceContext(
            origin_location_id=EntityId("loc-a"),
            destination_location_id=EntityId("loc-b"),
            affected_entity_ids=(EntityId("body-b"),),
        ),
    )
    batch = project_collapse_batch_events(
        (event,),
        tick=0,
        resulting_revision=1,
        registered_bodies=_registered(),
        location_regions=_regions(),
    )
    assert len(batch.receipts) == 1
    assert batch.receipts[0].site_location_id is None
    assert batch.receipts[0].attribution_gap is True


def test_unregistered_identity_is_attribution_gap() -> None:
    event = _event(
        event_id="help-1",
        sequence=1,
        details=Helped(
            target_id=EntityId("body-z"),
            health_delta=0.1,
            resulting_target_health=0.9,
            helper_fatigue_delta=0.05,
            resulting_helper_fatigue=0.2,
        ),
        actor_id=EntityId("body-a"),
    )
    batch = project_collapse_batch_events(
        (event,),
        tick=0,
        resulting_revision=1,
        registered_bodies=_registered(),
        location_regions=_regions(),
    )
    assert batch.receipts[0].counterpart_body_id is None
    assert batch.receipts[0].attribution_gap is True


def test_feed_contact_retained() -> None:
    event = _event(
        event_id="feed-1",
        sequence=1,
        details=Fed(
            target_id=EntityId("body-b"),
            item_id=EntityId("item-food"),
            item_kind="food",
            hunger_delta=-0.2,
            resulting_target_hunger=0.4,
        ),
        actor_id=EntityId("body-a"),
    )
    batch = project_collapse_batch_events(
        (event,),
        tick=0,
        resulting_revision=1,
        registered_bodies=_registered(),
        location_regions=_regions(),
    )
    assert batch.receipts[0].kind is CollapseReceiptKind.FEED_CONTACT


def test_death_with_incomplete_location_partial() -> None:
    event = _event(
        event_id="died-1",
        sequence=1,
        details=Died(body_id=EntityId("body-a"), death_cause=DeathCause.COMBINED_NEEDS),
        origin_location_id=EntityId("loc-unknown"),
    )
    batch = project_collapse_batch_events(
        (event,),
        tick=0,
        resulting_revision=1,
        registered_bodies=_registered(),
        location_regions=_regions(),
    )
    assert batch.receipts[0].kind is CollapseReceiptKind.DEATH
    assert batch.receipts[0].site_region_id is None


def test_frame_from_resilience_drops_stocks_and_held_items() -> None:
    from simulation.resilience_evidence import (
        ResilienceBodyRow,
        ResilienceOwnerKeys,
        ResilienceStockRow,
    )

    facts = ResilienceBoundaryFacts(
        run_id=_RUN,
        config_fingerprint="cfg-1",
        boundary_tick=0,
        revision=0,
        body_projection_hash=None,
        history_length=0,
        infrastructure_channel=OwnerLaneState.OFF,
        ecology_channel=OwnerLaneState.COMPLETE,
        bodies=(
            ResilienceBodyRow(
                body_id="body-a",
                agent_id="agent-a",
                living=True,
                held_item_count=3,
                region_id=None,
            ),
        ),
        stocks=(
            ResilienceStockRow(
                stock_id="stock-1",
                resource_kind="water",
                unit="unit",
                quantity_tenths=10,
                effective_capacity_tenths=10,
            ),
        ),
        infrastructure=(),
        owners=(
            ResilienceOwnerKeys(
                agent_id="agent-a",
                body_id="body-a",
                living=True,
                institution_state=OwnerLaneState.OFF,
                knowledge_state=OwnerLaneState.OFF,
                recognized_concept_ids=(),
                active_content_keys=(),
            ),
        ),
    )
    frame = frame_from_resilience_boundary(facts)
    assert frame.bodies[0].living is True
    assert not hasattr(frame.bodies[0], "held_item_count")
    assert "stocks" not in frame.__dataclass_fields__


def _plain_config(*, max_ticks: int = 2):
    body = alive_body("body-a", location_id="loc-a")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=41,
        stochastic_identity="collapse-capture",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-collapse-cap"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location("loc-a"),),
            bodies=(body,),
            weather=(make_weather("loc-a", condition=WeatherCondition.CLEAR),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=max_ticks,
    )


@pytest.mark.asyncio
async def test_capture_disabled_invokes_runner_once() -> None:
    config = replace(
        _plain_config(max_ticks=2),
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(
            max_ticks=2,
            stop_on_all_agents_terminal=False,
        ),
    )
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-collapse-off"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        captured = await run_with_collapse_recovery_capture(runner, capture=False)
    assert captured.status == "disabled"
    assert captured.evidence is None
    assert captured.report is None
    assert captured.result.ticks_committed == 2


@pytest.mark.asyncio
async def test_non_disasters_opt_in_accepted() -> None:
    config = replace(
        _plain_config(max_ticks=3),
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(
            max_ticks=3,
            stop_on_all_agents_terminal=False,
        ),
    )
    assert getattr(config, "disasters", None) is None
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-collapse-on"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        captured = await run_with_collapse_recovery_capture(runner, capture=True)
    assert captured.status in {"captured", "sealed"}
    assert captured.evidence is not None
    evidence = captured.evidence.evidence
    assert evidence.frames[0].tick == 0
    assert evidence.captured_through == captured.result.ticks_committed
    assert evidence.committed_through == captured.result.ticks_committed
    assert len(evidence.frames) == captured.result.ticks_committed + 1
    assert len(evidence.batches) == captured.result.ticks_committed
    assert evidence.source_coverage.regions_migration is False


@pytest.mark.asyncio
async def test_empty_batches_preserved_and_terminal_sampled_once() -> None:
    config = replace(
        _plain_config(max_ticks=2),
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(
            max_ticks=2,
            stop_on_all_agents_terminal=False,
        ),
    )
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-collapse-empty"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        captured = await run_with_collapse_recovery_capture(runner, capture=True)
    assert captured.evidence is not None
    evidence = captured.evidence.evidence
    assert all(batch.raw_event_count >= 0 for batch in evidence.batches)
    assert evidence.frames[-1].tick == 2


@pytest.mark.asyncio
async def test_projection_error_after_initial_does_not_change_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from experiments import collapse_recovery_capture as module

    config = replace(
        _plain_config(max_ticks=2),
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(
            max_ticks=2,
            stop_on_all_agents_terminal=False,
        ),
    )
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-collapse-proj"),
        factories=RunnerDependencyFactories(),
    )
    calls = {"n": 0}
    original = module._sample_boundary

    async def _flaky(runner_arg, *, accumulator, expect_batch):
        calls["n"] += 1
        if calls["n"] == 1:
            return await original(
                runner_arg, accumulator=accumulator, expect_batch=expect_batch
            )
        raise RuntimeError("export boom")

    monkeypatch.setattr(module, "_sample_boundary", _flaky)
    async with runner:
        captured = await run_with_collapse_recovery_capture(runner, capture=True)
    assert captured.result.ticks_committed == 2
    assert captured.status == "sealed"
    assert captured.evidence is not None
    assert captured.evidence.evidence.frames[0].tick == 0


@pytest.mark.asyncio
async def test_stale_batch_tick_seals_without_accepting() -> None:
    from experiments import collapse_recovery_capture as module
    from simulation.resilience_evidence import ResilienceBodyRow

    accumulator = module._Accumulator(
        run_id=_RUN,
        config_fingerprint="cfg-1",
        region_ids=(),
        location_regions={},
        source_coverage=CollapseSourceCoverage(
            regions_migration=False,
            resource_exchange=False,
            production=False,
            infrastructure=OwnerLaneState.OFF,
        ),
    )
    baseline = frame_from_resilience_boundary(
        ResilienceBoundaryFacts(
            run_id=_RUN,
            config_fingerprint="cfg-1",
            boundary_tick=0,
            revision=0,
            body_projection_hash=None,
            history_length=0,
            infrastructure_channel=OwnerLaneState.OFF,
            ecology_channel=OwnerLaneState.OFF,
            bodies=(
                ResilienceBodyRow(
                    body_id="body-a",
                    agent_id="agent-a",
                    living=True,
                    held_item_count=0,
                    region_id=None,
                ),
            ),
            stocks=(),
            infrastructure=(),
            owners=(),
        )
    )
    assert accumulator.accept_frame(baseline, batch=None)
    facts = ResilienceBoundaryFacts(
        run_id=_RUN,
        config_fingerprint="cfg-1",
        boundary_tick=1,
        revision=1,
        body_projection_hash="hash-1",
        history_length=0,
        infrastructure_channel=OwnerLaneState.OFF,
        ecology_channel=OwnerLaneState.OFF,
        bodies=(
            ResilienceBodyRow(
                body_id="body-a",
                agent_id="agent-a",
                living=True,
                held_item_count=0,
                region_id=None,
            ),
        ),
        stocks=(),
        infrastructure=(),
        owners=(),
    )
    next_frame = frame_from_resilience_boundary(facts)
    stale = CollapseBatch(
        tick=99,
        resulting_revision=1,
        raw_event_count=0,
        receipts=(),
    )
    accepted = accumulator.accept_frame(next_frame, batch=stale)
    assert accepted is False
    assert accumulator.seal_reason == "batch_tick_mismatch"


@pytest.mark.asyncio
async def test_capture_rejects_non_bool_flag() -> None:
    config = replace(
        _plain_config(max_ticks=1),
        mortality_mode=MortalityMode.DISABLED,
    )
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-collapse-bool"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        with pytest.raises(TypeError):
            await run_with_collapse_recovery_capture(runner, capture=1)  # type: ignore[arg-type]
