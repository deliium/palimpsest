# mypy: ignore-errors
"""In-process V4-14 migration scenario with real ticks, publication, and routes.

Runs in the focused/unit lane. Never requires PostgreSQL, Docker, network, or an
external LLM provider. Never reported as integration-only.
"""

from __future__ import annotations

import asyncio
import dataclasses
import os
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from agents.cognition.migration_displacement import (
    IntegrationStatus,
    MigrationCauseKind,
    MigrationCauseSource,
    MigrationDisplacementLedger,
    apply_migration_displacement_update,
    default_migration_displacement_policy,
    empty_migration_displacement_ledger,
    migration_displacement_update_summary,
)
from agents.cognition.migration_displacement_communication import (
    MIGRATION_FRAME_SUBJECT,
    MigrationFrame,
    MigrationFrameAct,
    migration_displacement_claim_relation,
)
from agents.models import AgentId
from api.dependencies import get_migration_displacement_reader, get_settings
from api.errors import ApiError, api_error_handler
from api.migration_displacement_cursor import MigrationDisplacementCursorCodec
from api.routes.migration_displacement import router
from experiments.collectors import assemble_arm_metric_bundle
from experiments.migration_displacement_publication import (
    build_migration_displacement_harvest_result,
)
from infrastructure.settings import Settings
from persistence.migration_displacement_filesystem import (
    create_migration_displacement_publisher,
    create_migration_displacement_reader,
)
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.models import SimulationRunConfig
from tests.physical_helpers import stressed_body
from tests.simulation_helpers import connected_locations, weather_for_locations
from world.actions import Flee, Move, Tell, Wait
from world.communications import origin_utterance
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import HazardKind, ObservedKinshipVisible

pytestmark = pytest.mark.unit

A1 = AgentId("agent-1")
A2 = AgentId("agent-2")
A3 = AgentId("agent-3")
A4 = AgentId("agent-4")
B1 = EntityId("body-1")
B2 = EntityId("body-2")
B3 = EntityId("body-3")
B4 = EntityId("body-4")
LOC_A = EntityId("loc-a")
LOC_B = EntityId("loc-b")
LOC_C = EntityId("loc-c")
RUN = "run-migration-e2e"
TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
POLICY = default_migration_displacement_policy()

AGENTS = (A1, A2, A3, A4)
BODIES = (B1, B2, B3, B4)
BODY_OF = dict(zip(AGENTS, BODIES, strict=True))
AGENT_OF = dict(zip(BODIES, AGENTS, strict=True))


def _identity(owner: AgentId) -> SimpleNamespace:
    owner_body = BODY_OF[owner]
    counterparts = tuple(
        SimpleNamespace(entity_id=BODY_OF[other], agent_id=other)
        for other in AGENTS
        if other != owner
    )
    return SimpleNamespace(
        owner_id=owner,
        owner_entity_id=owner_body,
        counterparts=counterparts,
    )


def _frame(
    *,
    speaker: EntityId,
    cause_kind: MigrationCauseKind = MigrationCauseKind.CONFLICT,
) -> MigrationFrame:
    return MigrationFrame(
        act=MigrationFrameAct.REPORT_CAUSE,
        speaker_ref=speaker.value,
        subject_ref=speaker.value,
        origin_ref="",
        route_refs=(),
        destination_ref="",
        cause_kind=cause_kind,
        source_kind=MigrationCauseSource.TESTIMONY,
        cluster_ref=None,
        confidence_q=80,
        as_of_tick=1,
        evidence_ref=None,
        declared_provenance_ref="mdv-declared",
    )


def _tell(*, speaker: EntityId, recipient: EntityId, frame: MigrationFrame) -> Tell:
    return Tell(
        recipient_id=recipient,
        utterance=origin_utterance(
            text=MIGRATION_FRAME_SUBJECT,
            speaker_id=speaker,
            relations=migration_displacement_claim_relation(frame),
        ),
    )


def _bootstrap() -> WorldBootstrap:
    locations = connected_locations(
        ("loc-a", "Origin"),
        ("loc-b", "Route"),
        ("loc-c", "Haven"),
    )
    return WorldBootstrap(
        world_id=WorldId("world-migration-e2e"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(
            stressed_body(
                "body-1",
                location_id="loc-a",
                health=100,
                hunger=92,
                thirst=10,
                fatigue=0,
            ),
            stressed_body(
                "body-2",
                location_id="loc-a",
                health=100,
                hunger=88,
                thirst=12,
                fatigue=0,
            ),
            stressed_body(
                "body-3",
                location_id="loc-a",
                health=100,
                hunger=85,
                thirst=8,
                fatigue=0,
            ),
            stressed_body(
                "body-4",
                location_id="loc-a",
                health=100,
                hunger=40,
                thirst=5,
                fatigue=0,
            ),
        ),
        items=(),
        weather=weather_for_locations(locations),
        registrations=(
            AgentRegistration(A1, B1),
            AgentRegistration(A2, B2),
            AgentRegistration(A3, B3),
            AgentRegistration(A4, B4),
        ),
    )


def _observe(engine: WorldEngine, body_id: EntityId):
    batch = engine.observe()
    observation = next(
        item for item in batch.observations if item.observer_id == body_id
    )
    return batch, observation


def _submit(batch, agent_id: AgentId, command) -> ActionSubmission:
    return ActionSubmission(token=batch.token, agent_id=agent_id, command=command)


def _enrich(observation, *, hazards: bool = True):
    updates: dict[str, object] = {}
    if hazards and observation.hazard_kinds is None:
        updates["hazard_kinds"] = (HazardKind.HEAT,)
    if updates:
        return dataclasses.replace(observation, **updates)
    return observation


def _orgs(owner: AgentId) -> SimpleNamespace:
    return SimpleNamespace(
        owner_id=owner,
        concepts=(SimpleNamespace(concept_id="org-haven", status="offer"),),
    )


def _rules(owner: AgentId) -> SimpleNamespace:
    return SimpleNamespace(
        owner_id=owner,
        rules=(SimpleNamespace(rule_id="rule-exclusion", status="exclusion"),),
    )


def _conflict(owner: AgentId) -> SimpleNamespace:
    return SimpleNamespace(
        owner_id=owner,
        episodes=(SimpleNamespace(episode_id="conflict-origin", status="conflict"),),
    )


def _relationships(owner: AgentId) -> tuple[SimpleNamespace, ...]:
    peers = [agent for agent in AGENTS if agent != owner][:2]
    return tuple(
        SimpleNamespace(source_id=owner, target_id=peer) for peer in peers
    )


def _kin(owner: AgentId) -> ObservedKinshipVisible:
    peers = sorted(agent.value for agent in AGENTS if agent != owner)[:2]
    return ObservedKinshipVisible(parents=(peers[0],), children=(peers[1],))


def _apply(
    owner: AgentId,
    observation,
    prior: MigrationDisplacementLedger,
    *,
    tick: int,
) -> MigrationDisplacementLedger:
    body = getattr(observation, "self_body", None)
    if body is not None and getattr(body, "kinship_visible", None) is None:
        observation = dataclasses.replace(
            observation,
            self_body=dataclasses.replace(body, kinship_visible=_kin(owner)),
        )
    return apply_migration_displacement_update(
        owner_id=owner,
        tick=tick,
        observation=_enrich(observation),
        prior=prior,
        identity=_identity(owner),
        policy=POLICY,
        organization_concepts=_orgs(owner),
        formal_rules=_rules(owner),
        organized_conflict=_conflict(owner),
        relationships=_relationships(owner),
    )


def _real_world_run() -> tuple[
    tuple[MigrationDisplacementLedger, ...],
    tuple[object, ...],
]:
    engine = WorldEngine(
        config=SimulationRunConfig(seed=41),
        bootstrap=_bootstrap(),
    )
    ledgers = {agent: empty_migration_displacement_ledger(agent) for agent in AGENTS}
    events: list[object] = []

    # Tick 0: three founders move independently toward the route node; one waits.
    batch, _ = _observe(engine, B1)
    result = engine.resolve_tick(
        (
            _submit(batch, A1, Move(destination_id=LOC_B)),
            _submit(batch, A2, Move(destination_id=LOC_B)),
            _submit(batch, A3, Flee()),
            _submit(batch, A4, Wait()),
        )
    )
    events.extend(record.event for record in result.events)

    # Tick 1: one mover delivers an mdp_v1 cause frame; others keep moving.
    batch, _ = _observe(engine, B2)
    result = engine.resolve_tick(
        (
            _submit(batch, A1, Wait()),
            _submit(
                batch,
                A2,
                _tell(
                    speaker=B2,
                    recipient=B1,
                    frame=_frame(speaker=B2),
                ),
            ),
            _submit(batch, A3, Move(destination_id=LOC_B)),
            _submit(batch, A4, Wait()),
        )
    )
    events.extend(record.event for record in result.events)
    for agent, body in BODY_OF.items():
        _, observation = _observe(engine, body)
        ledgers[agent] = _apply(agent, observation, ledgers[agent], tick=1)

    # Tick 2: two movers continue to the haven (opportunity destination).
    batch, _ = _observe(engine, B1)
    result = engine.resolve_tick(
        (
            _submit(batch, A1, Move(destination_id=LOC_C)),
            _submit(batch, A2, Move(destination_id=LOC_C)),
            _submit(batch, A3, Wait()),
            _submit(batch, A4, Wait()),
        )
    )
    events.extend(record.event for record in result.events)
    for agent, body in BODY_OF.items():
        _, observation = _observe(engine, body)
        ledgers[agent] = _apply(agent, observation, ledgers[agent], tick=2)

    # Tick 3: one settles at haven, one returns (integration diversity).
    batch, _ = _observe(engine, B1)
    result = engine.resolve_tick(
        (
            _submit(batch, A1, Wait()),
            _submit(batch, A2, Move(destination_id=LOC_B)),
            _submit(batch, A3, Wait()),
            _submit(batch, A4, Wait()),
        )
    )
    events.extend(record.event for record in result.events)
    for agent, body in BODY_OF.items():
        _, observation = _observe(engine, body)
        ledgers[agent] = _apply(agent, observation, ledgers[agent], tick=3)

    # Tick 4: settle residence long enough for a settled classification path.
    for tick in (4, 5, 6, 18, 19, 20):
        batch, _ = _observe(engine, B1)
        result = engine.resolve_tick(
            tuple(_submit(batch, agent, Wait()) for agent in AGENTS)
        )
        events.extend(record.event for record in result.events)
        for agent, body in BODY_OF.items():
            _, observation = _observe(engine, body)
            ledgers[agent] = _apply(agent, observation, ledgers[agent], tick=tick)

    return tuple(ledgers[agent] for agent in AGENTS), tuple(events)


def _runner(ledgers, events):
    agents = tuple(
        SimpleNamespace(agent_id=agent, entity_id=BODY_OF[agent]) for agent in AGENTS
    )
    return SimpleNamespace(
        stop_reason=SimpleNamespace(value="max_ticks"),
        status="completed",
        ticks_committed=21,
        migration_displacement_ledgers=tuple(ledgers),
        committed_events=tuple(events),
        assignment=SimpleNamespace(
            run_id=SimpleNamespace(value=RUN),
            runner_config=SimpleNamespace(
                agents=agents,
                regions_migration=None,
                scenario=None,
            ),
        ),
        runner_result=None,
        config_fingerprint="rev-migration-e2e-determinism-check-01",
    )


def _publish_and_read(tmp_path, ledgers, events):
    runner = _runner(ledgers, events)
    runner.runner_result = runner
    harvest_result = build_migration_displacement_harvest_result(
        runner,
        committed_events=events,
        run_id=RUN,
        input_revision="rev-migration-e2e",
        entity_to_agent={body.value: agent.value for agent, body in BODY_OF.items()},
    )
    assert harvest_result.receipt.status == "published"
    assert harvest_result.snapshot is not None
    snapshot = harvest_result.snapshot
    assert snapshot.movements
    assert snapshot.causes
    assert snapshot.waves
    assert snapshot.summary.wave_count >= 1

    root = tmp_path / "store"
    os.environ["PALIMPSEST_MIGRATION_DISPLACEMENT_ROOT"] = str(root)
    create_migration_displacement_publisher(root).publish(snapshot)

    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(
        api_debug_enabled=True,
        api_debug_credential=SecretStr(TOKEN),
    )
    app.dependency_overrides[get_settings] = lambda: settings
    reader = create_migration_displacement_reader(root)
    app.dependency_overrides[get_migration_displacement_reader] = lambda: reader
    app.state.migration_displacement_reader = reader
    app.state.migration_displacement_cursor_codec = MigrationDisplacementCursorCodec(
        b"k" * 32, now=lambda: 0.0
    )

    wave_token = snapshot.waves[0].wave_token

    async def call_routes():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            paths = (
                f"/v1/simulations/{RUN}/migration",
                f"/v1/simulations/{RUN}/migration/waves",
                f"/v1/simulations/{RUN}/migration/waves/{wave_token}",
                f"/v1/simulations/{RUN}/migration/routes",
                f"/v1/simulations/{RUN}/migration/causes",
                f"/v1/simulations/{RUN}/migration/outcomes",
            )
            responses = [await client.get(path, headers=HEADERS) for path in paths]
            waves_page = await client.get(
                f"/v1/simulations/{RUN}/migration/waves?limit=1", headers=HEADERS
            )
            cursor = waves_page.json().get("next_cursor")
            reuse = None
            invalid = None
            if cursor is not None:
                reuse = await client.get(
                    f"/v1/simulations/{RUN}/migration/waves?limit=1&cursor={cursor}",
                    headers=HEADERS,
                )
                invalid = await client.get(
                    f"/v1/simulations/{RUN}/migration/causes?cursor={cursor}",
                    headers=HEADERS,
                )
            return responses, reuse, invalid, snapshot, harvest_result

    return asyncio.run(call_routes())


def test_real_world_ticks_publication_metrics_and_all_six_routes(tmp_path) -> None:
    first_ledgers, first_events = _real_world_run()
    second_ledgers, second_events = _real_world_run()
    assert [item.digest for item in first_ledgers] == [
        item.digest for item in second_ledgers
    ]
    assert len(first_events) == len(second_events)

    ledgers = first_ledgers
    events = first_events
    event_kinds = {
        getattr(getattr(event, "details", None), "kind", None) for event in events
    }
    assert {"move", "tell"} <= event_kinds or {"move", "flee", "tell"} <= event_kinds

    # Owner ledgers stay separate (no telepathy / shared raw ledger).
    assert len({ledger.owner_id for ledger in ledgers}) == 4
    assert len({ledger.digest for ledger in ledgers}) >= 2

    cause_kinds: set[str] = set()
    for ledger in ledgers:
        cause_kinds.update(row.cause_kind.value for row in ledger.causes)
        summary = migration_displacement_update_summary(ledger)
        assert summary["causes"] >= 0
    assert {
        "resource_scarcity",
        "environmental_hazard",
        "conflict",
        "opportunity",
        "social_network",
        "institution",
    } <= cause_kinds

    # Frame recipient may store testimony; movers without the frame still exist.
    frame_owner = ledgers[0]
    silent_owner = ledgers[2]
    assert frame_owner.owner_id != silent_owner.owner_id
    assert frame_owner.digest != silent_owner.digest

    integration_statuses = {
        row.status for ledger in ledgers for row in ledger.integrations
    }
    assert integration_statuses & {
        IntegrationStatus.SETTLED,
        IntegrationStatus.TRANSIENT,
        IntegrationStatus.RETURNED,
        IntegrationStatus.ONWARD,
    }

    responses, reuse, invalid, snapshot, harvest_result = _publish_and_read(
        tmp_path, ledgers, events
    )
    assert [response.status_code for response in responses] == [200] * 6
    for response in responses:
        text = response.text
        assert "agent-1" not in text
        assert "body-1" not in text
        assert "loc-a" not in text
        for forbidden in ("refugee", "wellbeing", "assimilation", "score"):
            assert forbidden not in text

    assert snapshot.summary.movement_count >= 2
    assert snapshot.summary.cause_count >= 6
    assert any(
        wave.displacement_classification == "displacement_like"
        or wave.independent_cause_count > 0
        for wave in snapshot.waves
    )
    assert any(len(wave.participant_tokens) >= 2 for wave in snapshot.waves)
    if reuse is not None:
        assert reuse.status_code == 200
    if invalid is not None:
        assert invalid.status_code == 400
        assert invalid.json()["detail"] == "migration_displacement_cursor_invalid"

    runner = _runner(ledgers, events)
    runner.runner_result = runner
    bundle = assemble_arm_metric_bundle(runner)
    documents = {doc.metric_family: doc for doc in bundle.documents}
    for family in (
        "migration_wave_structure",
        "migration_cause_evidence",
        "migration_cluster_cohesion",
        "migration_integration_outcome",
    ):
        assert family in documents
    assert harvest_result.receipt.status == "published"


def test_disabled_reader_and_unknown_wave_paths(tmp_path) -> None:
    ledgers, events = _real_world_run()
    runner = _runner(ledgers, events)
    harvest_result = build_migration_displacement_harvest_result(
        runner,
        committed_events=events,
        run_id=RUN,
        input_revision="rev-migration-e2e",
        entity_to_agent={body.value: agent.value for agent, body in BODY_OF.items()},
    )
    assert harvest_result.snapshot is not None
    root = tmp_path / "store"
    create_migration_displacement_publisher(root).publish(harvest_result.snapshot)

    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(
        api_debug_enabled=True,
        api_debug_credential=SecretStr(TOKEN),
    )
    app.dependency_overrides[get_settings] = lambda: settings

    async def disabled_and_missing():
        app.dependency_overrides[get_migration_displacement_reader] = lambda: None
        app.state.migration_displacement_reader = None
        app.state.migration_displacement_cursor_codec = None
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            disabled = await client.get(
                f"/v1/simulations/{RUN}/migration", headers=HEADERS
            )
        reader = create_migration_displacement_reader(root)
        app.dependency_overrides[get_migration_displacement_reader] = lambda: reader
        app.state.migration_displacement_reader = reader
        app.state.migration_displacement_cursor_codec = (
            MigrationDisplacementCursorCodec(b"k" * 32, now=lambda: 0.0)
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            missing = await client.get(
                f"/v1/simulations/{RUN}/migration/waves/mig-missing",
                headers=HEADERS,
            )
        return disabled, missing

    disabled, missing = asyncio.run(disabled_and_missing())
    assert disabled.status_code == 503
    assert disabled.json()["detail"] == "migration_displacement_disabled"
    assert missing.status_code == 404
    assert missing.json()["detail"] == "migration_displacement_not_found"
